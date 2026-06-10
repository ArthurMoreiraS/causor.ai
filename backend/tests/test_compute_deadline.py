"""TDD for compute_deadline — CPC counting rules over a ForensicCalendar.

Rules modeled:
- Business-day deadlines (CPC art. 219): count only business days.
- "Dia do começo" (publication base) is excluded; counting starts the next
  business day (CPC art. 224).
- Início and vencimento are protracted to the next business day if they fall
  on a non-expediente day (art. 224 §1).
"""

from datetime import date

import pytest

from app.prazo_engine.calendar import ForensicCalendar
from app.prazo_engine.deadline import DeadlineResult, compute_deadline


@pytest.fixture
def cal():
    return ForensicCalendar(
        holidays={date(2024, 9, 7), date(2024, 12, 25)},
        recess_periods=[(date(2024, 12, 20), date(2025, 1, 20))],
    )


def test_business_days_basic(cal):
    res = compute_deadline(date(2024, 9, 9), 15, calendar=cal)
    assert isinstance(res, DeadlineResult)
    assert res.data_inicio == date(2024, 9, 9)
    assert res.data_fatal == date(2024, 9, 30)
    assert res.dias == 15
    assert res.dias_uteis is True


def test_business_days_cross_recess(cal):
    res = compute_deadline(date(2024, 12, 13), 5, calendar=cal)
    assert res.data_fatal == date(2025, 1, 21)


def test_inicio_protracted_when_publication_on_non_business_day(cal):
    # Published on Saturday holiday 2024-09-07 -> base protracted to Mon 09-09.
    res = compute_deadline(date(2024, 9, 7), 5, calendar=cal)
    assert res.data_inicio == date(2024, 9, 9)
    assert res.data_fatal == date(2024, 9, 16)


def test_calendar_days_no_protraction_needed(cal):
    res = compute_deadline(date(2024, 12, 13), 5, calendar=cal, business_days=False)
    assert res.dias_uteis is False
    assert res.data_fatal == date(2024, 12, 18)


def test_calendar_days_vencimento_protracted_over_recess(cal):
    # 13 + 10 calendar days = 2024-12-23, inside recess -> protract to 2025-01-21.
    res = compute_deadline(date(2024, 12, 13), 10, calendar=cal, business_days=False)
    assert res.data_fatal == date(2025, 1, 21)


def test_zero_days_rejected(cal):
    with pytest.raises(ValueError):
        compute_deadline(date(2024, 9, 9), 0, calendar=cal)
