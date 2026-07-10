from app.agent_runtime.service import claim_next_command, complete_command, enqueue_command
from app.sor import models


def test_command_is_enqueued_once_and_claimed_once(db_session, seeded):
    usuario = db_session.query(models.Usuario).first()
    installation = models.AgentInstallation(
        escritorio_id=seeded.escritorio_id,
        usuario_id=usuario.id,
        nome="Agent",
        token_hash="b" * 64,
        ativo=True,
    )
    db_session.add(installation)
    db_session.flush()

    first = enqueue_command(
        db_session,
        escritorio_id=seeded.escritorio_id,
        usuario_id=usuario.id,
        tipo="read_process",
        idempotency_key="read:instance:1:generation:1",
        payload={"processo_instancia_id": 1},
    )
    second = enqueue_command(
        db_session,
        escritorio_id=seeded.escritorio_id,
        usuario_id=usuario.id,
        tipo="read_process",
        idempotency_key="read:instance:1:generation:1",
        payload={"processo_instancia_id": 1},
    )
    assert first.id == second.id

    claimed = claim_next_command(db_session, installation=installation)
    assert claimed.id == first.id
    assert claim_next_command(db_session, installation=installation) is None

    complete_command(
        db_session,
        command=claimed,
        installation=installation,
        resultado={"status": "complete"},
    )
    assert claimed.status == "completed"
