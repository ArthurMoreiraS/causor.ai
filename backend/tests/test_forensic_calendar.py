"""TDD for ForensicCalendar — pure, deterministic business-day logic."""

from datetime import date

import pytest

from app.prazo_engine.calendar import ForensicCalendar


@pytest.fixture
def cal():
    # 2024-09-07 (Sat) Independência, 2024-12-25 (Wed) Natal as holidays.
    # Recess: 2024-12-20 .. 2025-01-20 inclusive.
    return ForensicCalendar(
        holidays={date(2024, 9, 7), date(2024, 12, 25)},
        recess_periods=[(date(2024, 12, 20), date(2025, 1, 20))],
    )


def test_weekday_is_business_day(cal):
    assert cal.is_business_day(date(2024, 9, 9))  # Monday


@pytest.mark.parametrize("d", [date(2024, 9, 14), date(2024, 9, 15)])  # Sat, Sun
def test_weekend_is_not_business_day(cal, d):
    assert not cal.is_business_day(d)


def test_holiday_is_not_business_day(cal):
    assert not cal.is_business_day(date(2024, 12, 25))


def test_recess_day_is_not_business_day(cal):
    # 2025-01-02 is a Thursday but inside the recess window.
    assert not cal.is_business_day(date(2025, 1, 2))


def test_recess_boundaries_inclusive(cal):
    assert not cal.is_business_day(date(2024, 12, 20))
    assert not cal.is_business_day(date(2025, 1, 20))
    # 2025-01-21 is the first business day after recess (Tuesday).
    assert cal.is_business_day(date(2025, 1, 21))


def test_next_business_day_skips_weekend(cal):
    # Friday 2024-09-13 -> next business day Monday 2024-09-16.
    assert cal.next_business_day(date(2024, 9, 13)) == date(2024, 9, 16)


def test_next_business_day_is_strictly_after(cal):
    # From a business day, returns the following business day.
    assert cal.next_business_day(date(2024, 9, 9)) == date(2024, 9, 10)


def test_next_business_day_jumps_recess(cal):
    # Thursday before recess -> first business day after recess.
    assert cal.next_business_day(date(2024, 12, 19)) == date(2025, 1, 21)


def test_previous_business_day(cal):
    # Monday 2024-09-16 -> previous business day Friday 2024-09-13.
    assert cal.previous_business_day(date(2024, 9, 16)) == date(2024, 9, 13)


def test_add_business_days_counts_only_business_days(cal):
    # Start Monday 2024-09-09, add 5 business days -> Monday 2024-09-16.
    assert cal.add_business_days(date(2024, 9, 9), 5) == date(2024, 9, 16)


def test_add_business_days_zero_returns_same_day(cal):
    assert cal.add_business_days(date(2024, 9, 9), 0) == date(2024, 9, 9)
