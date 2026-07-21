import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.sor import models


def _usuario_id(db_session) -> int:
    return db_session.scalars(select(models.Usuario)).first().id


def test_mni_credencial_unique_por_escritorio_tribunal(db_session, seeded):
    db_session.add(models.MniCredencial(
        escritorio_id=seeded.escritorio_id, tribunal="TJMG",
        id_consultante="12345678900", referencia_vault="localdev://mni/x", ativo=True,
    ))
    db_session.flush()
    db_session.add(models.MniCredencial(
        escritorio_id=seeded.escritorio_id, tribunal="TJMG",
        id_consultante="98765432100", referencia_vault="localdev://mni/y", ativo=True,
    ))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_captura_autos_fonte_default_agente(db_session, seeded):
    instancia = models.ProcessoInstancia(
        processo_id=seeded.id, escritorio_id=seeded.escritorio_id,
        sistema="PJe", tribunal="TJMG", grau="1", status="active",
    )
    db_session.add(instancia)
    db_session.flush()
    capture = models.CapturaAutos(
        escritorio_id=seeded.escritorio_id,
        processo_instancia_id=instancia.id,
        generation=99,
        status="queued",
    )
    db_session.add(capture)
    db_session.flush()
    assert capture.fonte == "agente"
