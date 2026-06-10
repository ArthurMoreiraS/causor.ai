"""DB TDD for registrar_prazo — compute deadline from an intimacao and persist."""

from datetime import date

import pytest

from app.capture.registrar import registrar_prazo
from app.prazo_engine.factory import build_calendar
from app.sor import models


@pytest.fixture
def calendar():
    return build_calendar([2024, 2025])


@pytest.fixture
def setup(db_session):
    esc = models.Escritorio(nome="Escritório Teste")
    db_session.add(esc)
    db_session.flush()
    proc = models.Processo(escritorio_id=esc.id, numero="00000010020248260100", tribunal="TJSP")
    db_session.add(proc)
    db_session.flush()
    intimacao = models.Intimacao(
        processo_id=proc.id,
        fonte="DJEN",
        fonte_id="111",
        numero_processo="00000010020248260100",
        tipo_comunicacao="Intimação",
        data_disponibilizacao=date(2024, 9, 6),  # Friday
    )
    db_session.add(intimacao)
    db_session.flush()
    return esc, proc, intimacao


def test_registrar_prazo_persists_and_links(db_session, setup, calendar):
    _esc, proc, intimacao = setup
    prazo = registrar_prazo(db_session, intimacao, dias=15, calendar=calendar)
    db_session.flush()

    assert prazo.id is not None
    assert prazo.processo_id == proc.id
    assert prazo.intimacao_id == intimacao.id
    assert prazo.dias == 15
    assert prazo.dias_uteis is True


def test_publication_is_business_day_after_disponibilizacao(db_session, setup, calendar):
    # Disponibilizado Fri 09-06 -> publicado Mon 09-09 -> count starts Tue 09-10.
    _esc, _proc, intimacao = setup
    prazo = registrar_prazo(db_session, intimacao, dias=15, calendar=calendar)
    assert prazo.data_inicio == date(2024, 9, 9)
    assert prazo.data_fatal == date(2024, 9, 30)


def test_uses_data_publicacao_when_present(db_session, setup, calendar):
    _esc, _proc, intimacao = setup
    intimacao.data_publicacao = date(2024, 9, 9)
    prazo = registrar_prazo(db_session, intimacao, dias=5, calendar=calendar)
    # Count starts the business day after publicacao (09-09) = 09-10.
    assert prazo.data_inicio == date(2024, 9, 9)
    assert prazo.data_fatal == date(2024, 9, 16)


def test_calendar_days_flag(db_session, setup, calendar):
    _esc, _proc, intimacao = setup
    prazo = registrar_prazo(
        db_session, intimacao, dias=5, calendar=calendar, business_days=False
    )
    assert prazo.dias_uteis is False


def test_raises_without_any_base_date(db_session, setup, calendar):
    _esc, _proc, intimacao = setup
    intimacao.data_disponibilizacao = None
    intimacao.data_publicacao = None
    with pytest.raises(ValueError):
        registrar_prazo(db_session, intimacao, dias=15, calendar=calendar)
