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
) -> PollResult:
    result = PollResult()

    for comunicacao in djen.consultar(oab=oab, uf=uf, data_inicio=data_inicio, data_fim=data_fim):
        intimacao = normalize_intimacao(session, comunicacao, escritorio_id=escritorio_id)
        is_new = intimacao in session.new
        session.flush()

        if not is_new:
            continue
        result.intimacoes_novas += 1

        if comunicacao.numero_processo and comunicacao.tribunal:
            processo_dto = datajud.consultar_processo(
                intimacao.numero_processo, tribunal=comunicacao.tribunal
            )
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
