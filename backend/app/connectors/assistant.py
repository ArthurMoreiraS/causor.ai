"""Passo acionável do assistente JIT de acesso ao tribunal.

Decide o que a UI deve abrir a seguir quando o contexto do processo não está
pronto: parear o agente, logar no tribunal ou capturar os autos. Mantido fora
de ``autos.context`` para não criar ciclo de import (o gate chama esta função)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.capture.court_routing import resolve_route
from app.connectors import sessions as court_sessions
from app.sor import models

# Um agente é "online" se pulsou nos últimos 120s (o worker pulsa a cada 20s).
AGENT_ONLINE_WINDOW = timedelta(seconds=120)


def has_online_agent(session: Session, escritorio_id: int) -> bool:
    cutoff = datetime.now(timezone.utc) - AGENT_ONLINE_WINDOW
    rows = session.scalars(
        select(models.AgentInstallation).where(
            models.AgentInstallation.escritorio_id == escritorio_id,
            models.AgentInstallation.ativo.is_(True),
        )
    ).all()
    for row in rows:
        seen = row.last_seen_at
        if seen is None:
            continue
        if seen.tzinfo is None:
            seen = seen.replace(tzinfo=timezone.utc)
        if seen >= cutoff:
            return True
    return False


def route_for(processo: models.Processo, grau: str) -> dict:
    route = resolve_route(processo.tribunal, grau)
    sistema = processo.sistema or (route.sistema if route else None) or "PJe"
    tribunal = route.tribunal if route else (processo.tribunal or "DESCONHECIDO")
    return {"sistema": sistema, "tribunal": tribunal, "grau": grau}


def resolve_next_step(
    session: Session,
    *,
    processo: models.Processo,
    grau: str = "1",
    context_ready: bool,
) -> tuple[str | None, dict]:
    """Retorna ``(next_step, rota)``. ``next_step`` é ``None`` quando pronto."""
    rota = route_for(processo, grau)
    if context_ready:
        return None, rota
    if not has_online_agent(session, processo.escritorio_id):
        return "pair_agent", rota
    state = court_sessions.session_state_for(
        session,
        escritorio_id=processo.escritorio_id,
        sistema=rota["sistema"],
        tribunal=rota["tribunal"],
        grau=grau,
    )
    if state is None or state.status != "conectado":
        return "court_login", rota
    return "capture_autos", rota
