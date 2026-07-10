"""Pareamento e autenticação do agente local.

O código de pareamento e o token do agente nunca são persistidos em claro:
o backend guarda apenas SHA-256. O token bruto é exibido uma única vez no
pareamento; revogação é `ativo=False` na instalação.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.sor import models


class AgentAuthError(ValueError):
    pass


@dataclass(frozen=True)
class PairingSecret:
    code: str
    expires_at: datetime


def _digest(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_pairing_code(session: Session, *, usuario: models.Usuario) -> PairingSecret:
    raw = secrets.token_urlsafe(24)
    expires_at = _now() + timedelta(minutes=10)
    session.add(
        models.AgentPairingCode(
            escritorio_id=usuario.escritorio_id,
            usuario_id=usuario.id,
            code_hash=_digest(raw),
            expires_at=expires_at,
        )
    )
    session.flush()
    return PairingSecret(code=raw, expires_at=expires_at)


def consume_pairing_code(
    session: Session, *, code: str, installation_name: str, version: str
) -> tuple[models.AgentInstallation, str]:
    row = session.scalars(
        select(models.AgentPairingCode).where(models.AgentPairingCode.code_hash == _digest(code))
    ).first()
    now = _now()
    if row is None:
        raise AgentAuthError("invalid pairing code")
    if row.used_at is not None:
        raise AgentAuthError("pairing code already used")
    expires_at = row.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= now:
        raise AgentAuthError("pairing code expired")

    raw_token = secrets.token_urlsafe(32)
    installation = models.AgentInstallation(
        escritorio_id=row.escritorio_id,
        usuario_id=row.usuario_id,
        nome=installation_name,
        token_hash=_digest(raw_token),
        ativo=True,
        version=version,
        last_seen_at=now,
    )
    row.used_at = now
    session.add(installation)
    session.flush()
    return installation, raw_token


def authenticate_agent_token(session: Session, token: str) -> models.AgentInstallation:
    installation = session.scalars(
        select(models.AgentInstallation).where(
            models.AgentInstallation.token_hash == _digest(token),
            models.AgentInstallation.ativo.is_(True),
        )
    ).first()
    if installation is None:
        raise AgentAuthError("invalid agent token")
    installation.last_seen_at = _now()
    return installation
