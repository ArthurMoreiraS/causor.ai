from hashlib import sha256

from app.agent_runtime.service import enqueue_command
from app.sor import models


def _pair(client):
    code = client.post("/agent/pairing-codes").json()["code"]
    paired = client.post(
        "/agent/pair",
        json={"code": code, "installation_name": "Notebook jurídico", "version": "0.1.0"},
    ).json()
    return paired["installation"], paired["token"]


def test_claim_requires_agent_token(client, seeded):
    response = client.post("/agent/commands/claim")
    assert response.status_code == 401


def test_pair_claim_complete_flow(client, db_session, seeded):
    usuario = db_session.query(models.Usuario).first()
    installation, token = _pair(client)
    headers = {"Authorization": f"Agent {token}"}

    command = enqueue_command(
        db_session,
        escritorio_id=seeded.escritorio_id,
        usuario_id=usuario.id,
        tipo="read_process",
        idempotency_key="read:1:1",
        payload={"processo_instancia_id": 1},
    )
    db_session.commit()

    claimed = client.post("/agent/commands/claim", headers=headers).json()
    assert claimed["id"] == command.id
    assert claimed["status"] == "running"
    assert "token_hash" not in str(claimed)

    completed = client.post(
        f"/agent/commands/{command.id}/complete",
        headers=headers,
        json={"resultado": {"status": "complete"}},
    ).json()
    assert completed["status"] == "completed"

    # Completion is idempotent: repeating returns the same state, no 409.
    repeat = client.post(
        f"/agent/commands/{command.id}/complete",
        headers=headers,
        json={"resultado": {"status": "complete"}},
    )
    assert repeat.status_code == 200
    assert repeat.json()["status"] == "completed"


def test_command_of_other_tenant_is_404(client, db_session, seeded):
    _, token = _pair(client)
    headers = {"Authorization": f"Agent {token}"}

    other = models.Escritorio(nome="Outro escritório")
    db_session.add(other)
    db_session.flush()
    foreign = enqueue_command(
        db_session,
        escritorio_id=other.id,
        usuario_id=None,
        tipo="read_process",
        idempotency_key="read:x:1",
        payload={},
    )
    db_session.commit()

    response = client.post(
        f"/agent/commands/{foreign.id}/complete",
        headers=headers,
        json={"resultado": {}},
    )
    assert response.status_code == 404


def test_revoked_agent_gets_401(client, db_session, seeded):
    installation, token = _pair(client)
    headers = {"Authorization": f"Agent {token}"}

    assert client.delete(f"/agent/installations/{installation['id']}").status_code == 204
    assert client.post("/agent/commands/claim", headers=headers).status_code == 401


def test_local_upload_requires_tenant_prefix_and_verifies_hash(client, db_session, seeded, tmp_path, monkeypatch):
    from app import settings as settings_module

    monkeypatch.setattr(settings_module.settings, "object_store_local_path", str(tmp_path))
    _, token = _pair(client)
    headers = {"Authorization": f"Agent {token}"}
    data = b"%PDF-1.4\n%%EOF\n"
    digest = sha256(data).hexdigest()

    wrong_tenant = client.put(
        "/agent/uploads/local",
        params={"key": "tenant/999/doc.pdf"},
        headers=headers,
        content=data,
    )
    assert wrong_tenant.status_code == 403

    bad_hash = client.put(
        "/agent/uploads/local",
        params={"key": f"tenant/{seeded.escritorio_id}/doc.pdf"},
        headers={**headers, "x-causor-sha256": "0" * 64},
        content=data,
    )
    assert bad_hash.status_code == 400

    ok = client.put(
        "/agent/uploads/local",
        params={"key": f"tenant/{seeded.escritorio_id}/doc.pdf"},
        headers={
            **headers,
            "x-causor-sha256": digest,
            "x-causor-size": str(len(data)),
        },
        content=data,
    )
    assert ok.status_code == 200
    assert ok.json()["sha256"] == digest
