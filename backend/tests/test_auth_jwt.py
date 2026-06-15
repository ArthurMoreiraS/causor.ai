"""TDD da dependency de autenticação por JWT do Supabase."""

import time

import jwt
import pytest
from fastapi import HTTPException

from app.auth.jwt_auth import CurrentUser, get_current_user
from app.sor import models

SECRET = "test-secret"


def _token(sub: str, email: str, exp_delta: int = 3600) -> str:
    payload = {
        "sub": sub,
        "email": email,
        "aud": "authenticated",
        "exp": int(time.time()) + exp_delta,
    }
    return jwt.encode(payload, SECRET, algorithm="HS256")


@pytest.fixture
def _secret(monkeypatch):
    from app.auth import jwt_auth
    monkeypatch.setattr(jwt_auth.settings, "supabase_jwt_secret", SECRET)


def _make_user(db_session, sub=None, email="a@b.com"):
    esc = models.Escritorio(nome="E")
    db_session.add(esc)
    db_session.flush()
    u = models.Usuario(escritorio_id=esc.id, nome="Adv", email=email, supabase_user_id=sub)
    db_session.add(u)
    db_session.flush()
    return esc, u


def test_token_valido_resolve_usuario(db_session, _secret):
    esc, u = _make_user(db_session, sub="sub-1", email="a@b.com")
    cur = get_current_user(authorization=f"Bearer {_token('sub-1', 'a@b.com')}", session=db_session)
    assert isinstance(cur, CurrentUser)
    assert cur.usuario_id == u.id
    assert cur.escritorio_id == esc.id


def test_claim_on_first_login_grava_sub(db_session, _secret):
    esc, u = _make_user(db_session, sub=None, email="a@b.com")
    cur = get_current_user(authorization=f"Bearer {_token('sub-novo', 'a@b.com')}", session=db_session)
    assert cur.usuario_id == u.id
    db_session.refresh(u)
    assert u.supabase_user_id == "sub-novo"


def test_sem_header_401(db_session, _secret):
    with pytest.raises(HTTPException) as exc:
        get_current_user(authorization=None, session=db_session)
    assert exc.value.status_code == 401


def test_token_expirado_401(db_session, _secret):
    _make_user(db_session, sub="sub-1", email="a@b.com")
    with pytest.raises(HTTPException) as exc:
        get_current_user(
            authorization=f"Bearer {_token('sub-1', 'a@b.com', exp_delta=-10)}",
            session=db_session,
        )
    assert exc.value.status_code == 401


def test_token_valido_sem_usuario_403(db_session, _secret):
    with pytest.raises(HTTPException) as exc:
        get_current_user(
            authorization=f"Bearer {_token('sub-x', 'naoexiste@b.com')}",
            session=db_session,
        )
    assert exc.value.status_code == 403
