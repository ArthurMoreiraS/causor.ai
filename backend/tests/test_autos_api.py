import pytest
from sqlalchemy import select

from app.autos.context import ContextNotReadyError, require_ready_context
from app.sor import models


def test_captura_automatica_sem_mni_e_recusada_e_aponta_o_upload(client, db_session, seeded):
    response = client.post(f"/processos/{seeded.id}/autos/capturar", json={"graus": ["1"]})

    assert response.status_code == 409
    assert response.json()["detail"] == "sem_canal_automatico"
    assert db_session.scalars(select(models.CapturaAutos)).first() is None


def test_contexto_incompleto_indica_upload_manual(db_session, seeded):
    with pytest.raises(ContextNotReadyError) as exc:
        require_ready_context(db_session, processo=seeded, usuario_id=None, action="draft")

    assert exc.value.next_step == "upload_autos"
    assert exc.value.rota["tribunal"] == "TJSP"
