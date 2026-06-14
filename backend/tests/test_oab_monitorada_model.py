"""TDD for the OabMonitorada SOR model."""

import pytest
from sqlalchemy.exc import IntegrityError

from app.sor import models


@pytest.fixture
def escritorio(db_session):
    esc = models.Escritorio(nome="Escritório Teste")
    db_session.add(esc)
    db_session.flush()
    return esc


def test_defaults_ativo_and_intervalo(db_session, escritorio):
    oab = models.OabMonitorada(escritorio_id=escritorio.id, oab="12345", uf="SP")
    db_session.add(oab)
    db_session.flush()

    assert oab.id is not None
    assert oab.ativo is True
    assert oab.intervalo_horas == 12
    assert oab.ultima_captura_em is None
    assert oab.cursor_data is None


def test_unique_per_escritorio_oab_uf(db_session, escritorio):
    db_session.add(models.OabMonitorada(escritorio_id=escritorio.id, oab="12345", uf="SP"))
    db_session.flush()
    db_session.add(models.OabMonitorada(escritorio_id=escritorio.id, oab="12345", uf="SP"))
    with pytest.raises(IntegrityError):
        db_session.flush()
