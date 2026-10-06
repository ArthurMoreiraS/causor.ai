"""TDD da dependency de autenticação por JWT do Supabase."""

import time

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
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


def _es256_token(sub: str, email: str, private_key, exp_delta: int = 3600) -> str:
    payload = {
        "sub": sub,
        "email": email,
        "aud": "authenticated",
        "iss": "https://example.supabase.co/auth/v1",
        "exp": int(time.time()) + exp_delta,
    }
    return jwt.encode(payload, private_key, algorithm="ES256", headers={"kid": "test-key"})


@pytest.fixture
def _secret(monkeypatch):
    from app.auth import jwt_auth
    monkeypatch.setattr(jwt_auth.settings, "supabase_jwt_secret", SECRET)


@pytest.fixture
def _p256_key(monkeypatch):
    from app.auth import jwt_auth

    private_key = ec.generate_private_key(ec.SECP256R1())
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    monkeypatch.setattr(jwt_auth.settings, "supabase_jwt_secret", public_pem.decode())
    monkeypatch.setattr(jwt_auth.settings, "supabase_url", "https://example.supabase.co")
    return private_key


def test_jwks_validates_only_configured_project(db_session, monkeypatch):
    from app.auth import jwt_auth
    private = ec.generate_private_key(ec.SECP256R1())
    monkeypatch.setattr(jwt_auth.settings, "supabase_jwt_secret", "")
    monkeypatch.setattr(jwt_auth.settings, "supabase_url", "https://example.supabase.co")
    urls = []

    def public_key(token, url):
        urls.append(url)
        return private.public_key()

    monkeypatch.setattr(jwt_auth, "_public_key_from_jwks", public_key)
    _, user = _make_user(db_session, sub="sub-1")
    token = _es256_token("sub-1", user.email, private)
    assert get_current_user(authorization=f"Bearer {token}", session=db_session).usuario_id == user.id
    assert urls == ["https://example.supabase.co/auth/v1/.well-known/jwks.json"]


@pytest.mark.parametrize("database", [
    "postgresql+psycopg://postgres.abcdefghijklmnopqrst:fixture@aws-0-sa-east-1.pooler.supabase.com:6543/postgres",
    "postgresql+psycopg://postgres:fixture@db.abcdefghijklmnopqrst.supabase.co:5432/postgres",
])
def test_existing_supabase_dsn_is_trusted_fallback_without_changing_deploy(monkeypatch, database):
    from app.auth import jwt_auth
    monkeypatch.setattr(jwt_auth.settings, "supabase_url", "")
    monkeypatch.setattr(jwt_auth.settings, "database_url", database)
    assert jwt_auth._configured_issuer() == "https://abcdefghijklmnopqrst.supabase.co/auth/v1"


def test_fixed_pem_does_not_require_remote_jwks(db_session, _p256_key, monkeypatch):
    from app.auth import jwt_auth
    monkeypatch.setattr(jwt_auth.settings, "supabase_url", "")
    monkeypatch.setattr(jwt_auth.settings, "database_url", "sqlite:///:memory:")
    monkeypatch.setattr(jwt_auth, "_public_key_from_jwks", lambda *_: pytest.fail("must not fetch keys"))
    _, user = _make_user(db_session, sub="sub-1")
    token = _es256_token("sub-1", user.email, _p256_key)
    assert get_current_user(authorization=f"Bearer {token}", session=db_session).usuario_id == user.id


@pytest.mark.parametrize("configured", ["", "https://trusted.supabase.co"])
def test_untrusted_issuer_cannot_choose_jwks_or_claim_user(db_session, monkeypatch, configured):
    from app.auth import jwt_auth
    private = ec.generate_private_key(ec.SECP256R1())
    monkeypatch.setattr(jwt_auth.settings, "supabase_jwt_secret", "")
    monkeypatch.setattr(jwt_auth.settings, "supabase_url", configured)
    monkeypatch.setattr(jwt_auth.settings, "database_url", "sqlite:///:memory:")
    fetched = []
    monkeypatch.setattr(jwt_auth, "_public_key_from_jwks", lambda token, url: fetched.append(url) or private.public_key())
    _, user = _make_user(db_session)
    token = _es256_token("foreign-sub", user.email, private)
    with pytest.raises(HTTPException) as exc:
        get_current_user(authorization=f"Bearer {token}", session=db_session)
    assert exc.value.status_code == 401
    assert fetched == []
    assert user.supabase_user_id is None


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


def test_token_es256_p256_resolve_usuario(db_session, _p256_key):
    esc, u = _make_user(db_session, sub="sub-1", email="a@b.com")
    token = _es256_token("sub-1", "a@b.com", _p256_key)
    cur = get_current_user(authorization=f"Bearer {token}", session=db_session)
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
