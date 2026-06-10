"""compute_deadline — apply CPC counting rules over a ForensicCalendar.

Deterministic date math only. Claude may classify *what kind* of deadline an
intimation triggers (how many days, business vs. calendar), but the date
arithmetic itself lives here and is unit-tested.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from app.prazo_engine.calendar import ForensicCalendar


@dataclass(frozen=True)
class DeadlineResult:
    data_inicio: date  # protracted publication base ("dia do começo")
    data_fatal: date  # vencimento (last valid day, already protracted)
    dias: int
    dias_uteis: bool


def compute_deadline(
    publication: date,
    days: int,
    *,
    calendar: ForensicCalendar,
    business_days: bool = True,
) -> DeadlineResult:
    """Compute a procedural deadline.

    Args:
        publication: the date the act is deemed published/intimated.
        days: the deadline length.
        calendar: holidays + recess source.
        business_days: True = count business days (CPC art. 219); False = count
            calendar days with the vencimento protracted to the next business day.
    """
    if days < 1:
        raise ValueError("days must be >= 1")

    # Protract the "dia do começo" to the next business day if needed.
    inicio = publication if calendar.is_business_day(publication) else calendar.next_business_day(
        publication
    )

    if business_days:
        # Counting excludes the start day; the Nth business day after it is the deadline.
        data_fatal = calendar.add_business_days(inicio, days)
    else:
        data_fatal = inicio + timedelta(days=days)
        if not calendar.is_business_day(data_fatal):
            data_fatal = calendar.next_business_day(data_fatal)

    return DeadlineResult(
        data_inicio=inicio,
        data_fatal=data_fatal,
        dias=days,
        dias_uteis=business_days,
    )
