"""Gate de contexto acionável: diz ao assistente qual passo abrir."""

from datetime import datetime, timezone

from app.sor import models
from tests.conftest import seed_connected_court_session


def _online_agent(db_session, seeded):
    usuario = db_session.query(models.Usuario).first()
    inst = models.AgentInstallation(
        escritorio_id=seeded.escritorio_id,
        usuario_id=usuario.id,
        nome="Notebook",
        token_hash="d" * 64,
        ativo=True,
        last_seen_at=datetime.now(timezone.utc),
    )
    db_session.add(inst)
    db_session.flush()
    return inst


def test_next_step_pair_agent_when_no_online_agent(client, db_session, seeded):
    resp = client.get(f"/processos/{seeded.id}/contexto/proximo-passo")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ready"] is False
    assert body["next_step"] == "pair_agent"
    assert body["rota"]["sistema"]
    assert body["rota"]["grau"]


def test_next_step_court_login_when_agent_online_but_session_missing(client, db_session, seeded):
    _online_agent(db_session, seeded)
    resp = client.get(f"/processos/{seeded.id}/contexto/proximo-passo")
    assert resp.json()["next_step"] == "court_login"


def test_next_step_capture_autos_when_connected_but_no_capture(client, db_session, seeded):
    _online_agent(db_session, seeded)
    route_sistema = "e-SAJ"  # TJSP resolve e-SAJ
    seed_connected_court_session(
        db_session, escritorio_id=seeded.escritorio_id, sistema=route_sistema,
        tribunal="TJSP", grau="1",
    )
    resp = client.get(f"/processos/{seeded.id}/contexto/proximo-passo")
    assert resp.json()["next_step"] == "capture_autos"


def test_next_step_ready_when_context_complete(client, db_session, seeded):
    from tests.conftest import seed_ready_context

    _online_agent(db_session, seeded)
    seed_ready_context(db_session, seeded)
    resp = client.get(f"/processos/{seeded.id}/contexto/proximo-passo")
    body = resp.json()
    assert body["ready"] is True
    assert body["next_step"] is None


def test_next_step_404_for_other_tenant(client, db_session, seeded):
    other = models.Escritorio(nome="Outro")
    db_session.add(other)
    db_session.flush()
    proc = models.Processo(escritorio_id=other.id, numero="9", tribunal="TJSP")
    db_session.add(proc)
    db_session.flush()
    resp = client.get(f"/processos/{proc.id}/contexto/proximo-passo")
    assert resp.status_code == 404
