"""Quais prazos estão em alerta, e em que nível.

**Decisão única.** ``GET /alertas`` (o painel) e o notificador (o e-mail)
consomem esta função. Recalcular a regra em qualquer um dos dois faria a tela e
o aviso divergirem sobre o mesmo prazo — e o ``AGENTS.md`` proíbe um segundo
ponto de decisão.

``hoje`` é injetado em vez de lido de ``date.today()`` porque a classificação é
aritmética de datas e precisa ser testável sem congelar o relógio.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.sor import models

#: Fora desta janela o prazo não vira aviso. Alinhado ao radar do painel.
JANELA_DIAS = 3

NIVEIS = ("vencido", "d0", "d1", "d3")


@dataclass(frozen=True)
class PrazoEmAlerta:
    prazo: models.Prazo
    nivel: str
    dias_para_vencer: int


def classificar(dias_para_vencer: int) -> str:
    if dias_para_vencer < 0:
        return "vencido"
    if dias_para_vencer == 0:
        return "d0"
    if dias_para_vencer == 1:
        return "d1"
    return "d3"


def prazos_em_alerta(
    session: Session, *, escritorio_id: int, hoje: date
) -> list[PrazoEmAlerta]:
    """Prazos abertos do escritório dentro da janela, do mais crítico ao menos."""
    stmt = (
        select(models.Prazo)
        .where(models.Prazo.escritorio_id == escritorio_id)
        .where(models.Prazo.cumprido.is_(False))
        .where(models.Prazo.data_fatal <= hoje + timedelta(days=JANELA_DIAS))
        .order_by(models.Prazo.data_fatal.asc())
    )
    alertas: list[PrazoEmAlerta] = []
    for prazo in session.scalars(stmt):
        dias = (prazo.data_fatal - hoje).days
        alertas.append(
            PrazoEmAlerta(prazo=prazo, nivel=classificar(dias), dias_para_vencer=dias)
        )
    return alertas
