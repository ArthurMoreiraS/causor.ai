"""Entrega do aviso de prazo para fora do Causor.

Ordem que não pode inverter: **envia, depois marca**. Se o SMTP falhar, nada é
gravado e a próxima execução do cron tenta de novo. Marcar antes de enviar
transformaria uma indisponibilidade de e-mail em prazo perdido, que é a única
coisa que o produto promete evitar.

Um aviso por escritório e por execução, agrupando os prazos pendentes — não um
e-mail por prazo. Quatro e-mails na mesma manhã treinam o advogado a filtrar a
caixa.

Além dos níveis de vencimento (``alertas.radar``), todo prazo criado pela
análise automática gera um aviso ``novo`` assim que nasce, mesmo longe do
vencimento: o advogado fica sabendo da intimação sem abrir o Causor.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
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

#: Prazo que vale sem confirmação: confirmado ou calculado pela análise automática.
VIGENTES = frozenset({"confirmado", "calculado_a_revisar"})

#: Prazo criado há mais que isto não é "novo": ligar o SMTP não dispara o acervo.
JANELA_NOVO = timedelta(days=2)


class AlertSender(Protocol):
    def enviar(self, *, destinos: list[str], assunto: str, corpo: str) -> bool | None: ...


@dataclass
class DeliveryReport:
    simulated: int = 0
    failed: int = 0


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


def prazos_novos(session: Session, *, escritorio_id: int, hoje: date) -> list[PrazoEmAlerta]:
    """Prazos abertos criados nos últimos dois dias e ainda não vencidos."""
    inicio = datetime.combine(hoje - JANELA_NOVO, time.min, tzinfo=timezone.utc)
    fim = datetime.combine(hoje + timedelta(days=1), time.min, tzinfo=timezone.utc)
    stmt = (
        select(models.Prazo)
        .where(models.Prazo.escritorio_id == escritorio_id)
        .where(models.Prazo.cumprido.is_(False))
        .where(models.Prazo.data_fatal >= hoje)
        .where(models.Prazo.created_at >= inicio, models.Prazo.created_at < fim)
        .order_by(models.Prazo.data_fatal.asc())
    )
    return [
        PrazoEmAlerta(prazo=prazo, nivel="novo", dias_para_vencer=(prazo.data_fatal - hoje).days)
        for prazo in session.scalars(stmt)
    ]


def _situacao(prazo: models.Prazo) -> str:
    status = prazo.revisao_status
    if status == "confirmado":
        return "confirmado"
    if status == "calculado_a_revisar":
        return "calculado automaticamente; confira se quiser"
    if status == "triagem":
        return "triagem: prazo real não identificado, revise até esta data"
    return "revisão humana pendente"


def _linha(alerta: PrazoEmAlerta, processo_numero: str | None) -> str:
    descricao = alerta.prazo.descricao or "Prazo"
    processo = f" — processo {processo_numero}" if processo_numero else ""
    data = alerta.prazo.data_fatal.strftime("%d/%m/%Y")
    if alerta.nivel == "novo":
        return f"- {descricao}{processo}: vence {data} ({_situacao(alerta.prazo)})"
    rotulo = ROTULOS.get(alerta.nivel, alerta.nivel)
    return f"- {descricao}{processo}: {rotulo} ({data}; {_situacao(alerta.prazo)})"


def montar_corpo(session: Session, alertas: list[PrazoEmAlerta]) -> str:
    """Uma linha por prazo; quem já está no radar não se repete entre os novos."""
    radar = [a for a in alertas if a.nivel != "novo"]
    no_radar = {a.prazo.id for a in radar}
    novos = [a for a in alertas if a.nivel == "novo" and a.prazo.id not in no_radar]
    partes = []
    for titulo, grupo in (("Prazos que pedem atenção:", radar), ("Prazos novos:", novos)):
        if not grupo:
            continue
        linhas = []
        for alerta in grupo:
            processo = (
                session.get(models.Processo, alerta.prazo.processo_id)
                if alerta.prazo.processo_id is not None
                else None
            )
            linhas.append(_linha(alerta, processo.numero if processo else None))
        partes.append(f"{titulo}\n\n" + "\n".join(linhas))
    return (
        "\n\n".join(partes)
        + "\n\nAbra o Causor para ver a intimação, o cálculo do prazo e a minuta."
    )


def montar_assunto(alertas: list[PrazoEmAlerta]) -> str:
    total = len({a.prazo.id for a in alertas})
    radar = [a for a in alertas if a.nivel != "novo"]
    # Data de triagem ou sem origem conhecida não é anunciada como vencimento.
    vigentes = [a for a in radar if a.prazo.revisao_status in VIGENTES]
    if any(a.nivel == "vencido" for a in vigentes):
        return f"[Causor] {total} prazo(s) — há prazo VENCIDO"
    if any(a.nivel == "d0" for a in vigentes):
        return f"[Causor] {total} prazo(s) — vence HOJE"
    if len(vigentes) < len(radar):
        return f"[Causor] {total} prazo(s) — revisão urgente de data sugerida"
    if radar:
        return f"[Causor] {total} prazo(s) próximos do vencimento"
    return f"[Causor] {total} prazo(s) novo(s) das intimações capturadas"


def notificar_prazos(
    session: Session,
    *,
    sender: AlertSender,
    hoje: date | None = None,
    escritorio_id: int | None = None,
    report: DeliveryReport | None = None,
) -> list[models.NotificacaoPrazo]:
    """Avisa cada escritório sobre os prazos ainda não avisados naquele nível."""
    hoje = hoje or date.today()
    report = report or DeliveryReport()
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
            for a in (
                *prazos_em_alerta(session, escritorio_id=escritorio.id, hoje=hoje),
                *prazos_novos(session, escritorio_id=escritorio.id, hoje=hoje),
            )
            if (a.prazo.id, a.nivel) not in avisados
        ]
        if not pendentes:
            continue

        try:
            delivered = sender.enviar(
                destinos=destinos,
                assunto=montar_assunto(pendentes),
                corpo=montar_corpo(session, pendentes),
            )
            if delivered is False:
                report.simulated += 1
                session.add(models.AuditLog(
                    escritorio_id=escritorio.id, ator="system", acao="alerta_prazo_simulado",
                    entidade="escritorio", entidade_id=escritorio.id,
                    detalhe={"prazos": len(pendentes)},
                ))
                continue
        except Exception:  # noqa: BLE001 - falha de envio não pode perder o aviso
            report.failed += 1
            session.add(models.AuditLog(
                escritorio_id=escritorio.id, ator="system", acao="alerta_prazo_falhou",
                entidade="escritorio", entidade_id=escritorio.id,
                detalhe={"prazos": len(pendentes)},
            ))
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
                    "prazos": sorted({a.prazo.id for a in pendentes}),
                    "niveis": dict(Counter(a.nivel for a in pendentes)),
                },
            )
        )
        session.flush()

    return gravadas
