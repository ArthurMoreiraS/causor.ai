"""Ciclo de vida idempotente dos comandos do agente local.

Enfileirar é idempotente por ``(escritorio_id, idempotency_key)``; o claim usa
``SELECT ... FOR UPDATE SKIP LOCKED`` para que duas instalações nunca executem
o mesmo comando. Payload/resultado nunca carregam segredos.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.sor import models

_TRANSITIONS = {
    "queued": {"running", "cancelled"},
    "running": {"completed", "failed", "resultado_incerto"},
    "resultado_incerto": set(),
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
    target_installation_id: int | None = None,
) -> models.AgentCommand:
    existing = session.scalars(
        select(models.AgentCommand).where(
            models.AgentCommand.escritorio_id == escritorio_id,
            models.AgentCommand.idempotency_key == idempotency_key,
        )
    ).first()
    if existing is not None:
        if existing.usuario_id != usuario_id or existing.tipo != tipo:
            raise AgentCommandOwnershipError("idempotency key belongs to another authorized operation")
        return existing
    if target_installation_id is not None:
        target = session.get(models.AgentInstallation, target_installation_id)
        if target is None or target.escritorio_id != escritorio_id or target.usuario_id != usuario_id or not target.ativo:
            raise AgentCommandOwnershipError("target installation does not belong to the authorized user")
    command = models.AgentCommand(
        escritorio_id=escritorio_id,
        usuario_id=usuario_id,
        tipo=tipo,
        status="queued",
        idempotency_key=idempotency_key,
        payload=payload,
        installation_id=target_installation_id,
    )
    session.add(command)
    session.flush()
    return command


def claim_next_command(
    session: Session, *, installation: models.AgentInstallation, supported_types: list[str] | None = None,
) -> models.AgentCommand | None:
    if not installation.ativo:
        return None
    stmt = (
        select(models.AgentCommand)
        .where(
            models.AgentCommand.escritorio_id == installation.escritorio_id,
            models.AgentCommand.status == "queued",
            models.AgentCommand.usuario_id == installation.usuario_id,
            or_(models.AgentCommand.installation_id.is_(None), models.AgentCommand.installation_id == installation.id),
        )
        .order_by(models.AgentCommand.id)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if supported_types is not None:
        stmt = stmt.where(models.AgentCommand.tipo.in_(supported_types))
    try:
        guarded_version = tuple(int(part) for part in (installation.version or "").split(".")) >= (0, 2, 0)
    except ValueError:
        guarded_version = False
    if not guarded_version:
        stmt = stmt.where(models.AgentCommand.tipo.not_in(["prepare_filing", "submit_filing"]))
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
    command: models.AgentCommand, installation: models.AgentInstallation, *, require_lease: bool = True,
) -> None:
    if command.installation_id != installation.id or command.usuario_id != installation.usuario_id or not installation.ativo:
        raise AgentCommandOwnershipError(
            f"command {command.id} is not owned by installation {installation.id}"
        )
    if command.status == "running" and require_lease:
        beat = command.heartbeat_at or command.claimed_at
        if beat is None or _now() - beat.replace(tzinfo=beat.tzinfo or timezone.utc) > timedelta(seconds=90):
            raise AgentCommandTransitionError("command lease expired; stop and reconcile before retry")


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
    uncertain = erro_codigo == "result_uncertain" or (command.resultado or {}).get("checkpoint") == "submitting"
    _require_owner(command, installation, require_lease=False)
    if command.status in {"failed", "resultado_incerto"}:
        return command
    _transition(command, "resultado_incerto" if uncertain else "failed")
    command.erro_codigo = erro_codigo
    command.erro_detalhe = erro_detalhe
    command.completed_at = _now()
    session.flush()
    return command


def checkpoint_command(session, *, command, installation, stage):
    _require_owner(command, installation)
    if command.status != "running":
        raise AgentCommandTransitionError("command is not running")
    previous = (command.resultado or {}).get("checkpoint")
    allowed = {None: {"prepared", "awaiting_intervention"}, "awaiting_intervention": {"prepared"},
               "prepared": {"awaiting_intervention", "submitting"}, "submitting": set()}
    if stage not in allowed.get(previous, set()):
        raise AgentCommandTransitionError("invalid execution stage; reconcile before retry")
    command.resultado = {**(command.resultado or {}), "checkpoint": stage, "checkpoint_at": _now().isoformat()}
    session.flush()
    return command
