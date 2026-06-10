"""ForensicCalendar — deterministic business-day arithmetic.

A business day is any weekday that is not a holiday and not inside a court
recess period. This module is pure (no I/O, no LLM) so it is fully unit
testable, per the prazo_engine working agreement.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, timedelta

_SATURDAY = 5  # date.weekday(): Mon=0 .. Sun=6


class ForensicCalendar:
    def __init__(
        self,
        holidays: Iterable[date] | None = None,
        recess_periods: Iterable[tuple[date, date]] | None = None,
    ) -> None:
        self._holidays: frozenset[date] = frozenset(holidays or ())
        # Normalize each recess to (start, end) with start <= end.
        self._recess: tuple[tuple[date, date], ...] = tuple(
            (min(a, b), max(a, b)) for a, b in (recess_periods or ())
        )

    def is_business_day(self, d: date) -> bool:
        if d.weekday() >= _SATURDAY:
            return False
        if d in self._holidays:
            return False
        if any(start <= d <= end for start, end in self._recess):
            return False
        return True

    def next_business_day(self, d: date) -> date:
        """First business day strictly after ``d``."""
        current = d + timedelta(days=1)
        while not self.is_business_day(current):
            current += timedelta(days=1)
        return current

    def previous_business_day(self, d: date) -> date:
        """First business day strictly before ``d``."""
        current = d - timedelta(days=1)
        while not self.is_business_day(current):
            current -= timedelta(days=1)
        return current

    def add_business_days(self, start: date, days: int) -> date:
        """Add ``days`` business days to ``start``.

        ``days == 0`` returns ``start`` unchanged (no anchoring applied here);
        each unit advances to the next business day.
        """
        if days < 0:
            raise ValueError("days must be non-negative")
        current = start
        for _ in range(days):
            current = self.next_business_day(current)
        return current
