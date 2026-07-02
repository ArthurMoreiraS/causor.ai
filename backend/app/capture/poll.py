"""poll_oab — orchestrate one capture cycle for an OAB registration.

Pipeline per communication: DJEN capture -> normalize (dedup) -> DataJud
enrich -> register a provisional deadline. Clients and the calendar are
injected for testability; the CLI wires the real ones.

The deadline length (``dias_default``) is a provisional placeholder: precise
classification of the act (how many days, business vs. calendar) is the agent
layer's job. The deterministic engine computes the date once the length is set.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import httpx
from sqlalchemy.orm import Session

from app.capture.datajud import DatajudClient
from app.capture.djen import DjenClient
from app.capture.normalize import enrich_processo, normalize_intimacao
from app.capture.registrar import registrar_prazo
from app.prazo_engine.calendar import ForensicCalendar


@dataclass
class PollResult:
    intimacoes_novas: int = 0
    processos_enriquecidos: int = 0
    prazos_registrados: int = 0
    # Quando o DJEN fica instavel (500 "sistema muito ocupado" e comum em pico
    # do CNJ), guardamos o que ja foi capturado em vez de descartar tudo. O
    # chamador decide se commita o parcial (worker/scheduler) ou rollbacka (API
    # sincrona, mantendo o 502 mas sem perder o que passou pelo flush).
    djen_indisponivel: bool = False
    djen_erro: str | None = None


def _iter_comunicacoes(djen: DjenClient, *, oab: str, uf: str, data_inicio: date | None, data_fim: date | None, itens_por_pagina: int = 50):
    """Itera todas as paginas do DJEN ate esgotar.

    Uma falha de rede/timeout/5xx numa pagina interrompe a iteracao: as
    comunicacoes ja consumidas foram entregues (yield); o restante fica para o
    proximo ciclo. O DjenClient ja tenta varias vezes com backoff antes de
    desistir, entao aqui nao ha retry adicional.
    """
    pagina = 1
    while True:
        comunicacoes = djen.consultar(
            oab=oab, uf=uf, data_inicio=data_inicio, data_fim=data_fim,
            pagina=pagina, itens_por_pagina=itens_por_pagina,
        )
        if not comunicacoes:
            return
        for comunicacao in comunicacoes:
            yield comunicacao
        if len(comunicacoes) < itens_por_pagina:
            return
        pagina += 1


def poll_oab(
    session: Session,
    *,
    oab: str,
    uf: str,
    escritorio_id: int,
    djen: DjenClient,
    datajud: DatajudClient,
    calendar: ForensicCalendar,
    dias_default: int = 15,
    data_inicio: date | None = None,
    data_fim: date | None = None,
    itens_por_pagina: int = 50,
    enrich: bool = True,
) -> PollResult:
    """Roda um ciclo de captura para uma OAB.

    Resiliente a indisponibilidade do DJEN: se o servico cai no meio da
    paginacao, o que ja foi normalizado/enriquecido/registrado fica no `result`
    e `djen_indisponivel=True`. O chamador (worker/scheduler/API) decide o que
    fazer com a sessao — commit (preserva parcial) ou rollback.

    ``enrich=False`` pula o enriquecimento DataJud (chamadas por processo) — a
    captura fica rapida (so intimações + prazos), e o Processo fica como "shell"
    (numero/tribunal). O enriquecimento e feito on-demand quando a minuta e
    gerada (``draft_from_intimacao``), garantindo o contexto completo do
    processo sem travar a captura.
    """
    result = PollResult()

    iterador = _iter_comunicacoes(
        djen, oab=oab, uf=uf, data_inicio=data_inicio, data_fim=data_fim,
        itens_por_pagina=itens_por_pagina,
    )
    while True:
        try:
            comunicacao = next(iterador)
        except StopIteration:
            break
        except httpx.HTTPError as exc:
            result.djen_indisponivel = True
            result.djen_erro = str(exc)[:500]
            return result

        intimacao = normalize_intimacao(session, comunicacao, escritorio_id=escritorio_id)
        is_new = intimacao in session.new
        session.flush()

        if not is_new:
            continue
        result.intimacoes_novas += 1

        if enrich and comunicacao.numero_processo and comunicacao.tribunal:
            try:
                processo_dto = datajud.consultar_processo(
                    intimacao.numero_processo, tribunal=comunicacao.tribunal
                )
            except httpx.HTTPError:
                processo_dto = None
            if processo_dto is not None:
                processo = enrich_processo(session, processo_dto, escritorio_id=escritorio_id)
                session.flush()
                result.processos_enriquecidos += 1
                if intimacao.processo_id is None:
                    intimacao.processo_id = processo.id

        registrar_prazo(session, intimacao, dias=dias_default, calendar=calendar)
        session.flush()
        result.prazos_registrados += 1

    return result
