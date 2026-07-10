from app.agent_runtime.auth import (
    AgentAuthError,
    authenticate_agent_token,
    consume_pairing_code,
    create_pairing_code,
)
from app.sor import models


def test_pairing_code_is_single_use(db_session, seeded):
    usuario = db_session.query(models.Usuario).first()
    secret = create_pairing_code(db_session, usuario=usuario)
    installation, token = consume_pairing_code(
        db_session, code=secret.code, installation_name="Notebook jurídico", version="0.1.0"
    )
    assert token
    assert authenticate_agent_token(db_session, token).id == installation.id

    try:
        consume_pairing_code(
            db_session, code=secret.code, installation_name="Reuso", version="0.1.0"
        )
    except AgentAuthError as exc:
        assert "used" in str(exc)
    else:
        raise AssertionError("pairing code was reused")
