"""Login de tribunal via agente e estado de sessão derivado.

O acesso autenticado (cookie/perfil Playwright) vive só na máquina do
advogado. Aqui o backend apenas: (1) enfileira ``open_court_login`` para o
agente abrir o portal na tela do advogado; (2) registra o desfecho como
estado derivado por ``(sistema, tribunal, grau)``. Nenhum segredo entra em
payload, resultado ou banco.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent_runtime.service import enqueue_command
from app.sor import models

SESSION_STATUSES = {"desconectado", "conectando", "conectado", "expirado"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _get_or_create_state(
    session: Session,
    *,
    escritorio_id: int,
    sistema: str,
    tribunal: str,
    grau: str,
) -> models.CourtSessionState:
    state = session_state_for(
        session, escritorio_id=escritorio_id, sistema=sistema, tribunal=tribunal, grau=grau
    )
    if state is None:
        state = models.CourtSessionState(
            escritorio_id=escritorio_id,
            sistema=sistema,
            tribunal=tribunal,
            grau=grau,
            status="desconectado",
        )
        session.add(state)
        session.flush()
    return state


def session_state_for(
    session: Session,
    *,
    escritorio_id: int,
    sistema: str,
    tribunal: str,
    grau: str,
) -> models.CourtSessionState | None:
    return session.scalars(
        select(models.CourtSessionState).where(
            models.CourtSessionState.escritorio_id == escritorio_id,
            models.CourtSessionState.sistema == sistema,
            models.CourtSessionState.tribunal == tribunal,
            models.CourtSessionState.grau == grau,
        )
    ).first()


def request_court_login(
    session: Session,
    *,
    escritorio_id: int,
    usuario_id: int | None,
    sistema: str,
    tribunal: str,
    grau: str,
    url_login: str,
    processo_instancia_id: int | None,
) -> tuple[models.CourtSessionState, models.AgentCommand]:
    """Marca a rota como ``conectando`` e publica o comando de login.

    Idempotente por rota/hora: repetir o clique dentro da mesma hora reusa o
    comando pendente em vez de abrir duas janelas no agente.
    """
    state = _get_or_create_state(
        session, escritorio_id=escritorio_id, sistema=sistema, tribunal=tribunal, grau=grau
    )
    state.status = "conectando"
    state.last_error_code = None
    command = enqueue_command(
        session,
        escritorio_id=escritorio_id,
        usuario_id=usuario_id,
        tipo="open_court_login",
        idempotency_key=(
            f"court-login:{sistema.casefold()}:{tribunal.upper()}:{grau}:"
            f"{_now().strftime('%Y-%m-%dT%H')}"
        ),
        payload={
            "sistema": sistema,
            "tribunal": tribunal,
            "grau": grau,
            "url_login": url_login,
            "processo_instancia_id": processo_instancia_id,
        },
    )
    session.flush()
    return state, command


def apply_login_result(
    session: Session,
    *,
    command: models.AgentCommand,
    installation: models.AgentInstallation,
    resultado: dict,
) -> models.CourtSessionState:
    """Traduz a conclusão do ``open_court_login`` em estado derivado."""
    payload = command.payload
    state = _get_or_create_state(
        session,
        escritorio_id=command.escritorio_id,
        sistema=payload["sistema"],
        tribunal=payload["tribunal"],
        grau=payload["grau"],
    )
    if resultado.get("session_ready") is True:
        state.status = "conectado"
        state.installation_id = installation.id
        state.version_marker = resultado.get("version_marker")
        state.last_confirmed_at = _now()
        state.last_error_code = None
    else:
        state.status = "desconectado"
        state.last_error_code = resultado.get("error_code") or "login_not_confirmed"
    session.flush()
    return state


def apply_login_failure(
    session: Session,
    *,
    command: models.AgentCommand,
    installation: models.AgentInstallation,  # noqa: ARG001 - simetria com apply_login_result
    erro_codigo: str,
) -> models.CourtSessionState:
    payload = command.payload
    state = _get_or_create_state(
        session,
        escritorio_id=command.escritorio_id,
        sistema=payload["sistema"],
        tribunal=payload["tribunal"],
        grau=payload["grau"],
    )
    state.status = "desconectado"
    state.last_error_code = erro_codigo
    session.flush()
    return state


def mark_session_expired(
    session: Session,
    *,
    escritorio_id: int,
    sistema: str,
    tribunal: str,
    grau: str,
    error_code: str = "session_expired",
) -> models.CourtSessionState:
    """Chamado quando leitura/protocolo/health-check detecta sessão inválida."""
    state = _get_or_create_state(
        session, escritorio_id=escritorio_id, sistema=sistema, tribunal=tribunal, grau=grau
    )
    state.status = "expirado"
    state.last_error_code = error_code
    session.flush()
    return state
