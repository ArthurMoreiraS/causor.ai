"""Ciclo ponta a ponta do agente local (Marco A).

user pairing → agent pair → enqueue → claim → heartbeat → complete → audit.
"""

from app.agent_runtime.service import enqueue_command
from app.sor import models


def test_full_agent_lifecycle(client, db_session, seeded):
    usuario = db_session.query(models.Usuario).first()

    # Usuário autenticado (JWT) cria o código de pareamento.
    pairing = client.post("/agent/pairing-codes")
    assert pairing.status_code == 200
    code = pairing.json()["code"]

    # O agente consome o código sem JWT e recebe o token único.
    paired = client.post(
        "/agent/pair",
        json={"code": code, "installation_name": "Notebook jurídico", "version": "0.1.0"},
    )
    assert paired.status_code == 200
    token = paired.json()["token"]
    headers = {"Authorization": f"Agent {token}"}

    # Backend publica um comando idempotente.
    command = enqueue_command(
        db_session,
        escritorio_id=seeded.escritorio_id,
        usuario_id=usuario.id,
        tipo="read_process",
        idempotency_key="e2e:read:1",
        payload={"processo_instancia_id": 1},
    )
    db_session.commit()

    # Agente reivindica, pulsa e conclui.
    command_json = client.post("/agent/commands/claim", headers=headers).json()
    assert command_json["status"] == "running"
    assert command_json["id"] == command.id

    heartbeat = client.post(f"/agent/commands/{command.id}/heartbeat", headers=headers)
    assert heartbeat.status_code == 200

    completed = client.post(
        f"/agent/commands/{command.id}/complete",
        headers=headers,
        json={"resultado": {"status": "complete"}},
    )
    completed_json = completed.json()
    assert completed_json["status"] == "completed"
    assert "token_hash" not in str(completed_json)
    assert (
        db_session.query(models.AuditLog).filter_by(acao="agent_command_completed").count() == 1
    )
