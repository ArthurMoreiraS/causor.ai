"""Passo acionável do assistente JIT de acesso ao tribunal.

Decide o que a UI deve abrir a seguir quando o contexto do processo não está
pronto: parear o agente, logar no tribunal ou capturar os autos. Mantido fora
de ``autos.context`` para não criar ciclo de import (o gate chama esta função)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.capture.court_routing import resolve_route
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
    # Sem default de PJe: o sistema vem do processo, da rota conhecida, ou é
    # declaradamente desconhecido. Chutar mandava o advogado para o portal
    # errado sem avisar.
    sistema = processo.sistema or (route.sistema if route else None) or "DESCONHECIDO"
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

    # A ordem das regras vive em ``access_channel`` — aqui só se traduz a
    # capacidade "ler os autos" no passo que a UI abre. Recalcular a decisão
    # aqui criaria o segundo ponto de decisão que o AGENTS.md proíbe, e é o que
    # faria a tela prometer um estado que o sistema não entrega na hora H.
    from app.connectors.access_channel import resolve_acesso_tribunal

    acesso = resolve_acesso_tribunal(
        session,
        escritorio_id=processo.escritorio_id,
        sistema=rota["sistema"],
        tribunal=rota["tribunal"],
        grau=grau,
    )
    if acesso.ler_autos.disponivel:
        return "capture_autos", rota
    if acesso.ler_autos.falta == "integracao_indisponivel":
        return "upload_autos", rota
    if acesso.ler_autos.falta == "parear":
        return "pair_agent", rota
    return "court_login", rota
