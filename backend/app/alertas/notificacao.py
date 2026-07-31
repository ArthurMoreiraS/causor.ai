"""Entrega do aviso de prazo para fora do Causor.

Ordem que não pode inverter: **envia, depois marca**. Se o SMTP falhar, nada é
gravado e a próxima execução do cron tenta de novo. Marcar antes de enviar
transformaria uma indisponibilidade de e-mail em prazo perdido, que é a única
coisa que o produto promete evitar.

Um aviso por escritório e por execução, agrupando os prazos pendentes — não um
e-mail por prazo. Quatro e-mails na mesma manhã treinam o advogado a filtrar a
caixa.
"""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timezone
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.alertas.radar import PrazoEmAlerta, prazos_em_alerta
from app.sor import models

ROTULOS = {
    "vencido": "VENCIDO",
    "d0": "vence HOJE",
    "d1": "vence amanhã",
    "d3": "vence em 3 dias",
}


class AlertSender(Protocol):
    def enviar(self, *, destinos: list[str], assunto: str, corpo: str) -> None: ...


def _destinos(session: Session, escritorio_id: int) -> list[str]:
    emails = session.scalars(
        select(models.Usuario.email)
        .where(models.Usuario.escritorio_id == escritorio_id)
        .where(models.Usuario.email.is_not(None))
        .order_by(models.Usuario.id)
    ).all()
    return [e for e in emails if e]


def _ja_avisados(session: Session, escritorio_id: int) -> set[tuple[int, str]]:
    linhas = session.execute(
        select(models.NotificacaoPrazo.prazo_id, models.NotificacaoPrazo.nivel).where(
            models.NotificacaoPrazo.escritorio_id == escritorio_id
        )
    ).all()
    return {(prazo_id, nivel) for prazo_id, nivel in linhas}


def _linha(alerta: PrazoEmAlerta, processo_numero: str | None) -> str:
    rotulo = ROTULOS.get(alerta.nivel, alerta.nivel)
    descricao = alerta.prazo.descricao or "Prazo"
    processo = f" — processo {processo_numero}" if processo_numero else ""
    data = alerta.prazo.data_fatal.strftime("%d/%m/%Y")
    return f"- {descricao}{processo}: {rotulo} ({data})"


def montar_corpo(session: Session, alertas: list[PrazoEmAlerta]) -> str:
    linhas = []
    for alerta in alertas:
        processo = (
            session.get(models.Processo, alerta.prazo.processo_id)
            if alerta.prazo.processo_id is not None
            else None
        )
        linhas.append(_linha(alerta, processo.numero if processo else None))
    return (
        "Prazos que pedem atenção:\n\n"
        + "\n".join(linhas)
        + "\n\nAbra o Causor para ver a intimação, o cálculo do prazo e a minuta."
    )


def montar_assunto(alertas: list[PrazoEmAlerta]) -> str:
    if any(a.nivel == "vencido" for a in alertas):
        return f"[Causor] {len(alertas)} prazo(s) — há prazo VENCIDO"
    if any(a.nivel == "d0" for a in alertas):
        return f"[Causor] {len(alertas)} prazo(s) — vence HOJE"
    return f"[Causor] {len(alertas)} prazo(s) próximos do vencimento"


def notificar_prazos(
    session: Session,
    *,
    sender: AlertSender,
    hoje: date | None = None,
    escritorio_id: int | None = None,
) -> list[models.NotificacaoPrazo]:
    """Avisa cada escritório sobre os prazos ainda não avisados naquele nível."""
    hoje = hoje or date.today()
    escritorios = session.scalars(
        select(models.Escritorio).where(
            models.Escritorio.id == escritorio_id
            if escritorio_id is not None
            else models.Escritorio.id.is_not(None)
        )
    ).all()

    gravadas: list[models.NotificacaoPrazo] = []
    for escritorio in escritorios:
        destinos = _destinos(session, escritorio.id)
        if not destinos:
            # Sem para quem mandar: não grava nada, para o aviso sair assim que
            # o e-mail do escritório for cadastrado.
            continue

        avisados = _ja_avisados(session, escritorio.id)
        pendentes = [
            a
            for a in prazos_em_alerta(session, escritorio_id=escritorio.id, hoje=hoje)
            if (a.prazo.id, a.nivel) not in avisados
        ]
        if not pendentes:
            continue

        try:
            sender.enviar(
                destinos=destinos,
                assunto=montar_assunto(pendentes),
                corpo=montar_corpo(session, pendentes),
            )
        except Exception:  # noqa: BLE001 - falha de envio não pode perder o aviso
            continue

        agora = datetime.now(timezone.utc)
        for alerta in pendentes:
            registro = models.NotificacaoPrazo(
                escritorio_id=escritorio.id,
                prazo_id=alerta.prazo.id,
                nivel=alerta.nivel,
                destino=", ".join(destinos)[:500],
                enviado_em=agora,
            )
            session.add(registro)
            gravadas.append(registro)
        session.add(
            models.AuditLog(
                escritorio_id=escritorio.id,
                ator="system",
                acao="alerta_prazo_enviado",
                entidade="escritorio",
                entidade_id=escritorio.id,
                detalhe={
                    "destinos": len(destinos),
                    "prazos": [a.prazo.id for a in pendentes],
                    "niveis": dict(Counter(a.nivel for a in pendentes)),
                },
            )
        )
        session.flush()

    return gravadas
