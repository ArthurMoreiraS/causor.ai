"""registrar_prazo — turn a captured intimacao into a persisted deadline.

Resolves the publication base from the intimacao, runs the deterministic
prazo_engine, and writes a Prazo row linked back to the intimacao/processo.

Base-date rule (Lei 11.419/2006 art. 4 §3 + CPC art. 224):
- If ``data_publicacao`` is known, it is the publication.
- Otherwise the publication is the first business day after
  ``data_disponibilizacao``.
compute_deadline then excludes the publication day and counts from the next
business day.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.prazo_engine.calendar import ForensicCalendar
from app.prazo_engine.deadline import compute_deadline
from app.sor import models


def _resolve_publication(intimacao: models.Intimacao, calendar: ForensicCalendar) -> date:
    if intimacao.data_publicacao:
        return intimacao.data_publicacao
    if intimacao.data_disponibilizacao:
        return calendar.next_business_day(intimacao.data_disponibilizacao)
    raise ValueError("intimacao has no data_publicacao nor data_disponibilizacao")


def registrar_prazo(
    session: Session,
    intimacao: models.Intimacao,
    *,
    dias: int,
    calendar: ForensicCalendar,
    business_days: bool = True,
    descricao: str | None = None,
) -> models.Prazo:
    publication = _resolve_publication(intimacao, calendar)
    result = compute_deadline(
        publication, dias, calendar=calendar, business_days=business_days
    )

    prazo = models.Prazo(
        processo_id=intimacao.processo_id,
        intimacao_id=intimacao.id,
        descricao=descricao or intimacao.tipo_comunicacao,
        data_inicio=result.data_inicio,
        dias=result.dias,
        dias_uteis=result.dias_uteis,
        data_fatal=result.data_fatal,
    )
    session.add(prazo)
    return prazo
