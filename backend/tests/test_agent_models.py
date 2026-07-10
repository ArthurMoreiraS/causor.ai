from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError
import pytest

from app.sor import models


def test_process_can_have_first_and_second_degree_instances(db_session, seeded):
    first = models.ProcessoInstancia(
        processo_id=seeded.id,
        escritorio_id=seeded.escritorio_id,
        sistema="PJe",
        tribunal="TJMG",
        grau="1",
        url_base="https://pje.tjmg.jus.br/pje",
        status="active",
    )
    second = models.ProcessoInstancia(
        processo_id=seeded.id,
        escritorio_id=seeded.escritorio_id,
        sistema="PJe",
        tribunal="TJMG",
        grau="2",
        url_base="https://pje2g.tjmg.jus.br/pje",
        status="active",
    )
    db_session.add_all([first, second])
    db_session.flush()
    assert {item.grau for item in seeded.instancias} == {"1", "2"}


def test_agent_command_idempotency_is_tenant_scoped(db_session, seeded):
    command = dict(
        escritorio_id=seeded.escritorio_id,
        usuario_id=None,
        installation_id=None,
        tipo="read_process",
        status="queued",
        idempotency_key="capture:1:manifest:1",
        payload={"processo_instancia_id": 1},
    )
    db_session.add(models.AgentCommand(**command))
    db_session.flush()
    db_session.add(models.AgentCommand(**command))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_pairing_code_has_expiry_and_single_use_fields(db_session, seeded):
    usuario = db_session.query(models.Usuario).first()
    code = models.AgentPairingCode(
        escritorio_id=seeded.escritorio_id,
        usuario_id=usuario.id,
        code_hash="a" * 64,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
    )
    db_session.add(code)
    db_session.flush()
    assert code.used_at is None
