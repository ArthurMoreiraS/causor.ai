"""Ciclo de vida idempotente dos comandos do agente local.

Enfileirar é idempotente por ``(escritorio_id, idempotency_key)``; o claim usa
``SELECT ... FOR UPDATE SKIP LOCKED`` para que duas instalações nunca executem
o mesmo comando. Payload/resultado nunca carregam segredos.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.sor import models

_TRANSITIONS = {
    "queued": {"running", "cancelled"},
    "running": {"completed", "failed", "queued"},
    "completed": set(),
    "failed": set(),
    "cancelled": set(),
}


class AgentCommandTransitionError(RuntimeError):
    pass


class AgentCommandOwnershipError(RuntimeError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _transition(command: models.AgentCommand, new_status: str) -> None:
    if new_status not in _TRANSITIONS.get(command.status, set()):
        raise AgentCommandTransitionError(
            f"invalid transition {command.status} -> {new_status} for command {command.id}"
        )
    command.status = new_status


def enqueue_command(
    session: Session,
    *,
    escritorio_id: int,
    usuario_id: int | None,
    tipo: str,
    idempotency_key: str,
    payload: dict,
) -> models.AgentCommand:
    existing = session.scalars(
        select(models.AgentCommand).where(
            models.AgentCommand.escritorio_id == escritorio_id,
            models.AgentCommand.idempotency_key == idempotency_key,
        )
    ).first()
    if existing is not None:
        return existing
    command = models.AgentCommand(
        escritorio_id=escritorio_id,
        usuario_id=usuario_id,
        tipo=tipo,
        status="queued",
        idempotency_key=idempotency_key,
        payload=payload,
    )
    session.add(command)
    session.flush()
    return command


def claim_next_command(
    session: Session, *, installation: models.AgentInstallation
) -> models.AgentCommand | None:
    stmt = (
        select(models.AgentCommand)
        .where(
            models.AgentCommand.escritorio_id == installation.escritorio_id,
            models.AgentCommand.status == "queued",
        )
        .order_by(models.AgentCommand.id)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    command = session.scalars(stmt).first()
    if command is None:
        return None
    now = _now()
    _transition(command, "running")
    command.installation_id = installation.id
    command.claimed_at = now
    command.heartbeat_at = now
    session.flush()
    return command


def _require_owner(
    command: models.AgentCommand, installation: models.AgentInstallation
) -> None:
    if command.installation_id != installation.id:
        raise AgentCommandOwnershipError(
            f"command {command.id} is not owned by installation {installation.id}"
        )


def heartbeat_command(
    session: Session,
    *,
    command: models.AgentCommand,
    installation: models.AgentInstallation,
) -> models.AgentCommand:
    _require_owner(command, installation)
    if command.status != "running":
        raise AgentCommandTransitionError(
            f"cannot heartbeat command {command.id} in status {command.status}"
        )
    command.heartbeat_at = _now()
    session.flush()
    return command


def complete_command(
    session: Session,
    *,
    command: models.AgentCommand,
    installation: models.AgentInstallation,
    resultado: dict,
) -> models.AgentCommand:
    _require_owner(command, installation)
    if command.status == "completed":
        return command
    _transition(command, "completed")
    command.resultado = resultado
    command.completed_at = _now()
    session.flush()
    return command


def fail_command(
    session: Session,
    *,
    command: models.AgentCommand,
    installation: models.AgentInstallation,
    erro_codigo: str,
    erro_detalhe: str | None = None,
) -> models.AgentCommand:
    _require_owner(command, installation)
    if command.status == "failed":
        return command
    _transition(command, "failed")
    command.erro_codigo = erro_codigo
    command.erro_detalhe = erro_detalhe
    command.completed_at = _now()
    session.flush()
    return command
