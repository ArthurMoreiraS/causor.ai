"""Authentication dependency for Supabase-issued JWTs."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import httpx
import jwt
from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.settings import settings
from app.sor import models
from app.sor.db import get_session


@dataclass(frozen=True)
class CurrentUser:
    usuario_id: int
    escritorio_id: int
    email: str


def _normalize_pem(value: str) -> str:
    return value.strip().replace("\\n", "\n")


def _jwks_url_from_issuer(issuer: str | None) -> str:
    if not issuer:
        raise jwt.InvalidIssuerError("missing issuer")
    return f"{issuer.rstrip('/')}/.well-known/jwks.json"


@lru_cache(maxsize=8)
def _jwks_data(jwks_url: str) -> dict:
    try:
        response = httpx.get(jwks_url, timeout=10, trust_env=False)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise jwt.InvalidTokenError("unable to fetch JWKS") from exc
    return response.json()


def _public_key_from_jwks(token: str, jwks_url: str):
    kid = jwt.get_unverified_header(token).get("kid")
    for key_data in _jwks_data(jwks_url).get("keys", []):
        if key_data.get("kid") == kid:
            return jwt.PyJWK.from_dict(key_data).key
    raise jwt.InvalidTokenError("signing key not found")


def _decode_hs256(token: str) -> dict:
    if not settings.supabase_jwt_secret:
        raise jwt.InvalidKeyError("missing HS256 secret")
    return jwt.decode(
        token,
        settings.supabase_jwt_secret,
        algorithms=["HS256"],
        audience="authenticated",
    )


def _decode_es256(token: str) -> dict:
    claims = jwt.decode(token, options={"verify_signature": False})
    issuer = claims.get("iss")

    configured_key = _normalize_pem(settings.supabase_jwt_secret)
    if configured_key.startswith("-----BEGIN"):
        return jwt.decode(
            token,
            configured_key,
            algorithms=["ES256"],
            audience="authenticated",
            issuer=issuer,
        )

    signing_key = _public_key_from_jwks(token, _jwks_url_from_issuer(issuer))
    return jwt.decode(
        token,
        signing_key,
        algorithms=["ES256"],
        audience="authenticated",
        issuer=issuer,
    )


def decode_supabase_jwt(token: str) -> dict:
    try:
        alg = jwt.get_unverified_header(token).get("alg")
        if alg == "ES256":
            return _decode_es256(token)
        if alg == "HS256":
            return _decode_hs256(token)
        raise jwt.InvalidAlgorithmError(f"unsupported algorithm: {alg}")
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="token inválido") from exc


def get_current_user(
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_session),
) -> CurrentUser:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="autenticação requerida")
    token = authorization.split(" ", 1)[1].strip()
    claims = decode_supabase_jwt(token)
    sub = claims.get("sub")
    email = claims.get("email")

    usuario = session.scalars(
        select(models.Usuario).where(models.Usuario.supabase_user_id == sub)
    ).first()
    if usuario is None and email:
        usuario = session.scalars(
            select(models.Usuario).where(models.Usuario.email == email)
        ).first()
        if usuario is not None:
            usuario.supabase_user_id = sub  # claim on first login
            session.commit()  # persist link even for read-only requests
    if usuario is None:
        raise HTTPException(status_code=403, detail="usuário sem acesso")

    return CurrentUser(
        usuario_id=usuario.id,
        escritorio_id=usuario.escritorio_id,
        email=usuario.email,
    )
