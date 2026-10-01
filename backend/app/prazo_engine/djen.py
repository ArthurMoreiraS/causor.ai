"""DJEN civil publication and CPC counting are separate calendars."""

from dataclasses import dataclass
from datetime import date, timedelta

from app.prazo_engine.calendar import ForensicCalendar


@dataclass(frozen=True)
class DjenDeadline:
    disponibilizacao: date
    publicacao: date
    primeiro_dia: date
    data_fatal: date
    dias: int


def compute_djen_civil_deadline(
    disponibilizacao: date, dias: int, *,
    publication_calendar: ForensicCalendar,
    counting_calendar: ForensicCalendar,
    publication: date | None = None,
) -> DjenDeadline:
    """Publication follows the next court working day; counting starts after it.

    CPC recess suspends counting but does not postpone DJEN publication.
    """
    if not 1 <= dias <= 3650:
        raise ValueError("dias deve estar entre 1 e 3650")
    publicacao = publication or publication_calendar.next_business_day(disponibilizacao)
    if publicacao < disponibilizacao:
        raise ValueError("publicacao anterior a disponibilizacao")
    cursor = publicacao
    counted = 0
    first: date | None = None
    while counted < dias:
        cursor += timedelta(days=1)
        if counting_calendar.is_business_day(cursor):
            first = first or cursor
            counted += 1
    assert first is not None
    return DjenDeadline(disponibilizacao, publicacao, first, cursor, dias)
