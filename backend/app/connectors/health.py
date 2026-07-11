"""Health-check read-only de perfis de conector.

Enfileira no máximo um comando ``health_check`` por perfil a cada 24h (chave de
idempotência por dia). O comando verifica marcador de login/versão e a URL do
perfil sem abrir ou baixar um processo real. Falha de marcador rebaixa o
estado efetivo para ``degraded`` — nunca edita o perfil de código.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.agent_runtime.service import enqueue_command
from app.connectors.coverage import known_profiles
from app.sor import models


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def enqueue_connector_health_checks(
    session: Session, *, escritorio_id: int, usuario_id: int | None = None
) -> list[models.AgentCommand]:
    """Um health_check read-only por perfil/dia (idempotente)."""
    commands: list[models.AgentCommand] = []
    for profile in known_profiles():
        command = enqueue_command(
            session,
            escritorio_id=escritorio_id,
            usuario_id=usuario_id,
            tipo="health_check",
            idempotency_key=f"connector-health:{profile.key}:{_today()}",
            payload={
                "profile_key": profile.key,
                "sistema": profile.sistema,
                "tribunal": profile.tribunal,
                "grau": profile.grau,
                "url_login": profile.url_base,
                "version_marker": profile.version_marker,
            },
        )
        commands.append(command)
    return commands
