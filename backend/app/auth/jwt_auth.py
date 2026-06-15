"""Autenticação por JWT do Supabase.

Valida o token (HS256 com o segredo do projeto), resolve o Usuario do SOR e
expõe um CurrentUser. O segredo vem de settings/env e nunca é logado.
"""

from __future__ import annotations

from dataclasses import dataclass

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


def decode_supabase_jwt(token: str) -> dict:
    if not settings.supabase_jwt_secret:
        raise HTTPException(status_code=500, detail="auth não configurado")
    try:
        return jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
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
            session.flush()
    if usuario is None:
        raise HTTPException(status_code=403, detail="usuário sem acesso")

    return CurrentUser(
        usuario_id=usuario.id,
        escritorio_id=usuario.escritorio_id,
        email=usuario.email,
    )
