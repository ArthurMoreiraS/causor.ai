"""build_calendar — assemble a ForensicCalendar for Brazilian forensic practice.

Combines national holidays (via workalendar) with the forensic recess window
(20/12 .. 20/01, CPC art. 220), during which procedural deadlines are suspended.

Local (municipal/state) holidays and per-court suspensions are layered on top
by callers as they become known; this factory provides the national baseline.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date

from workalendar.america import Brazil

from app.prazo_engine.calendar import ForensicCalendar

_RECESS_START = (12, 20)
_RECESS_END = (1, 20)


def build_calendar(
    years: Iterable[int],
    extra_holidays: Iterable[date] | None = None,
) -> ForensicCalendar:
    cal = Brazil()
    years = list(years)

    holidays: set[date] = set(extra_holidays or ())
    for year in years:
        for holiday_date, _name in cal.holidays(year):
            holidays.add(holiday_date)

    # Recess spanning each listed year-end into the following January.
    recess_periods: list[tuple[date, date]] = [
        (date(year, *_RECESS_START), date(year + 1, *_RECESS_END)) for year in years
    ]

    return ForensicCalendar(holidays=holidays, recess_periods=recess_periods)
