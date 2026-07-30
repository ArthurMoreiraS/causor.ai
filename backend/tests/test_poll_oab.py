"""TDD for poll_oab orchestration with injected fake clients."""

from datetime import date

import httpx
import pytest

from app.capture.datajud import ProcessoDTO
from app.capture.djen import ComunicacaoDTO
from app.capture.poll import UnboundedCaptureError, poll_oab
from app.prazo_engine.factory import build_calendar
from app.sor import models


# Toda captura de teste roda com janela e "hoje" explicitos: poll_oab exige
# limite de data (captura sem janela varre o historico inteiro da OAB) e o prazo
# provisorio so e registrado se ainda estiver vigente. Pinar aqui evita que os
# asserts passem a depender do relogio da maquina.
JANELA = {
    "data_inicio": date(2024, 9, 1),
    "data_fim": date(2024, 9, 30),
    "hoje": date(2024, 9, 9),
}


class FakeDjen:
    def __init__(self, items):
        self._items = items
        self.calls = []

    def consultar(self, oab, uf, **kw):
        self.calls.append((oab, uf, kw))
        return self._items


class FakeDatajud:
    def __init__(self, by_numero):
        self._by_numero = by_numero
        self.calls = []

    def consultar_processo(self, numero_processo, *, tribunal):
        self.calls.append((numero_processo, tribunal))
        return self._by_numero.get(numero_processo)


class TimeoutDatajud:
    def __init__(self):
        self.calls = []

    def consultar_processo(self, numero_processo, *, tribunal):
        self.calls.append((numero_processo, tribunal))
        raise httpx.ReadTimeout("The read operation timed out")


@pytest.fixture
def calendar():
    return build_calendar([2024, 2025])


@pytest.fixture
def escritorio(db_session):
    esc = models.Escritorio(nome="Escritório Teste")
    db_session.add(esc)
    db_session.flush()
    return esc


def _comunicacao(fonte_id="111"):
    return ComunicacaoDTO.from_item(
        {
            "id": fonte_id,
            "numero_processo": "0000001-00.2024.8.26.0100",
            "siglaTribunal": "TJSP",
            "tipoComunicacao": "Intimação",
            "texto": "Intimada para manifestar em 15 dias.",
            "data_disponibilizacao": "2024-09-06",
        }
    )


def _processo_dto():
    return ProcessoDTO.from_source(
        {
            "numeroProcesso": "00000010020248260100",
            "classe": {"nome": "Procedimento Comum Cível"},
            "tribunal": "TJSP",
            "sistema": {"nome": "PJe"},
            "movimentos": [
                {"codigo": 26, "nome": "Distribuição", "dataHora": "2024-01-15T10:00:00.000Z"},
            ],
        }
    )


def test_poll_captures_normalizes_enriches_and_registers(db_session, escritorio, calendar):
    djen = FakeDjen([_comunicacao()])
    datajud = FakeDatajud({"00000010020248260100": _processo_dto()})

    result = poll_oab(
        db_session,
        oab="12345",
        uf="SP",
        escritorio_id=escritorio.id,
        djen=djen,
        datajud=datajud,
        calendar=calendar,
        dias_default=15, **JANELA,
    )

    assert result.intimacoes_novas == 1
    assert result.processos_enriquecidos == 1
    assert result.prazos_registrados == 1

    intimacao = db_session.query(models.Intimacao).one()
    processo = db_session.query(models.Processo).one()
    prazo = db_session.query(models.Prazo).one()
    assert intimacao.processo_id == processo.id
    assert processo.sistema == "PJe"
    assert prazo.data_inicio == date(2024, 9, 9)
    assert prazo.data_fatal == date(2024, 9, 30)
    assert djen.calls[0][0] == "12345"


def test_poll_is_idempotent_on_rerun(db_session, escritorio, calendar):
    djen = FakeDjen([_comunicacao()])
    datajud = FakeDatajud({"00000010020248260100": _processo_dto()})
    args = dict(
        oab="12345", uf="SP", escritorio_id=escritorio.id,
        djen=djen, datajud=datajud, calendar=calendar, dias_default=15, **JANELA,
    )

    poll_oab(db_session, **args)
    second = poll_oab(db_session, **args)

    assert second.intimacoes_novas == 0
    assert second.prazos_registrados == 0
    assert db_session.query(models.Intimacao).count() == 1
    assert db_session.query(models.Prazo).count() == 1


def test_poll_without_datajud_match_still_registers(db_session, escritorio, calendar):
    djen = FakeDjen([_comunicacao()])
    datajud = FakeDatajud({})  # no process found

    result = poll_oab(
        db_session, oab="12345", uf="SP", escritorio_id=escritorio.id,
        djen=djen, datajud=datajud, calendar=calendar, dias_default=15, **JANELA,
    )

    assert result.intimacoes_novas == 1
    assert result.processos_enriquecidos == 0
    assert result.prazos_registrados == 1
    assert db_session.query(models.Prazo).count() == 1


def test_poll_datajud_timeout_still_registers_deadline(db_session, escritorio, calendar):
    djen = FakeDjen([_comunicacao()])
    datajud = TimeoutDatajud()

    result = poll_oab(
        db_session, oab="12345", uf="SP", escritorio_id=escritorio.id,
        djen=djen, datajud=datajud, calendar=calendar, dias_default=15, **JANELA,
    )

    assert result.intimacoes_novas == 1
    assert result.processos_enriquecidos == 0
    assert result.prazos_registrados == 1
    assert db_session.query(models.Intimacao).count() == 1
    assert db_session.query(models.Processo).count() == 1
    assert db_session.query(models.Prazo).count() == 1


class PagedDjen:
    """Fake DJEN that simulates multiple pages of results.

    The real API returns at most ``itens_por_pagina`` per call and returns an
    empty list once past the last page. Each call records the page requested.
    """

    def __init__(self, items, page_size):
        self._items = items
        self._page_size = page_size
        self.calls = []

    def consultar(self, oab, uf, *, pagina=1, itens_por_pagina=50, **kw):
        self.calls.append((oab, uf, pagina, itens_por_pagina, kw))
        start = (pagina - 1) * itens_por_pagina
        end = start + itens_por_pagina
        return self._items[start:end]


def test_poll_iterates_all_djen_pages(db_session, escritorio, calendar):
    """A volume-heavy OAB should pull all pages, not just the first 50."""
    items = [_comunicacao(fonte_id=str(i)) for i in range(120)]
    djen = PagedDjen(items, page_size=50)
    datajud = FakeDatajud({})

    result = poll_oab(
        db_session, oab="12345", uf="SP", escritorio_id=escritorio.id,
        djen=djen, datajud=datajud, calendar=calendar, dias_default=15, **JANELA,
        itens_por_pagina=50,
    )

    # 120 itens / 50 por pagina -> 3 paginas (50, 50, 20)
    paginas_pedidas = [c[2] for c in djen.calls]
    assert paginas_pedidas == [1, 2, 3]
    assert result.intimacoes_novas == 120
    assert db_session.query(models.Intimacao).count() == 120


def test_poll_stops_when_page_underfilled(db_session, escritorio, calendar):
    """If a page returns fewer than itens_por_pagina, we stop paging."""
    items = [_comunicacao(fonte_id=str(i)) for i in range(30)]
    djen = PagedDjen(items, page_size=50)

    result = poll_oab(
        db_session, oab="12345", uf="SP", escritorio_id=escritorio.id,
        djen=djen, datajud=FakeDatajud({}), calendar=calendar, dias_default=15, **JANELA,
    )

    assert [c[2] for c in djen.calls] == [1]  # so a primeira pagina
    assert result.intimacoes_novas == 30


def test_poll_empty_djen_returns_no_pages_beyond_first(db_session, escritorio, calendar):
    """An OAB with no comunicacoes should make exactly one DJEN call."""
    djen = PagedDjen([], page_size=50)

    poll_oab(
        db_session, oab="12345", uf="SP", escritorio_id=escritorio.id,
        djen=djen, datajud=FakeDatajud({}), calendar=calendar, dias_default=15, **JANELA,
    )

    assert len(djen.calls) == 1  # uma unica chamada para confirmar empty
    assert djen.calls[0][2] == 1


def test_poll_enrich_false_skips_datajud_and_is_fast(db_session, escritorio, calendar):
    """enrich=False: captura intimações + prazos mas NAO chama DataJud.
    O processo fica como "shell" (numero/tribunal), enriquecido on-demand na minuta."""
    djen = FakeDjen([_comunicacao()])
    datajud = FakeDatajud({"00000010020248260100": _processo_dto()})

    result = poll_oab(
        db_session, oab="12345", uf="SP", escritorio_id=escritorio.id,
        djen=djen, datajud=datajud, calendar=calendar, dias_default=15, **JANELA,
        enrich=False,
    )

    assert result.intimacoes_novas == 1
    assert result.processos_enriquecidos == 0  # DataJud nao foi chamado
    assert result.prazos_registrados == 1
    assert datajud.calls == []  # zero chamadas DataJud
    # Processo "shell" existe mas sem andamentos nem classe
    processo = db_session.query(models.Processo).one()
    assert processo.numero == "00000010020248260100"
    assert processo.classe is None
    assert db_session.query(models.Andamento).count() == 0


def test_poll_oab_recusa_captura_sem_janela(db_session, escritorio, calendar):
    """Sem janela, o DJEN devolve o histórico inteiro da OAB.

    A API ordena do mais novo para o mais antigo e `_iter_comunicacoes` pagina
    até esgotar: em produção isso varreu uma OAB de 626 comunicações até
    fevereiro quando o chamador esqueceu as datas. Tem de falhar alto, antes de
    bater na rede — não rodar quieto.
    """
    djen = FakeDjen([_comunicacao()])

    with pytest.raises(UnboundedCaptureError):
        poll_oab(
            db_session,
            oab="12345",
            uf="SP",
            escritorio_id=escritorio.id,
            djen=djen,
            datajud=FakeDatajud({}),
            calendar=calendar,
        )

    assert djen.calls == []


def test_poll_oab_permite_historico_completo_quando_explicito(db_session, escritorio, calendar):
    """A varredura completa continua possível — mas só sob pedido explícito."""
    djen = FakeDjen([])

    poll_oab(
        db_session,
        oab="12345",
        uf="SP",
        escritorio_id=escritorio.id,
        djen=djen,
        datajud=FakeDatajud({}),
        calendar=calendar,
        historico_completo=True,
    )

    assert djen.calls[0][2]["data_inicio"] is None


def test_poll_oab_nao_fabrica_prazo_ja_vencido(db_session, escritorio, calendar):
    """`dias_default` é um chute provisório; sobre publicação antiga ele produz
    um vencimento que já passou. Registrar isso enche o painel de risco de
    alarme falso (foi o que gerou 130 prazos vencidos num piloto real).
    """
    djen = FakeDjen([_comunicacao()])

    result = poll_oab(
        db_session,
        oab="12345",
        uf="SP",
        escritorio_id=escritorio.id,
        djen=djen,
        datajud=FakeDatajud({}),
        calendar=calendar,
        dias_default=15,
        data_inicio=date(2024, 9, 1),
        data_fim=date(2024, 9, 30),
        hoje=date(2026, 7, 29),
    )

    assert result.intimacoes_novas == 1
    assert result.prazos_registrados == 0
    assert result.prazos_historicos == 1
    assert db_session.query(models.Prazo).count() == 0
    # A intimação continua no SOR — nada é perdido, só não vira alarme.
    assert db_session.query(models.Intimacao).count() == 1
