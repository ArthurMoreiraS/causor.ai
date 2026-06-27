"""TDD for poll_oab orchestration with injected fake clients."""

from datetime import date

import httpx
import pytest

from app.capture.datajud import ProcessoDTO
from app.capture.djen import ComunicacaoDTO
from app.capture.poll import poll_oab
from app.prazo_engine.factory import build_calendar
from app.sor import models


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
        dias_default=15,
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
        djen=djen, datajud=datajud, calendar=calendar, dias_default=15,
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
        djen=djen, datajud=datajud, calendar=calendar, dias_default=15,
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
        djen=djen, datajud=datajud, calendar=calendar, dias_default=15,
    )

    assert result.intimacoes_novas == 1
    assert result.processos_enriquecidos == 0
    assert result.prazos_registrados == 1
    assert db_session.query(models.Intimacao).count() == 1
    assert db_session.query(models.Processo).count() == 1
    assert db_session.query(models.Prazo).count() == 1
