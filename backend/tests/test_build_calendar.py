"""TDD for build_calendar — assembles a ForensicCalendar from workalendar."""

from datetime import date

from app.prazo_engine.calendar import ForensicCalendar
from app.prazo_engine.factory import build_calendar


def test_returns_forensic_calendar():
    assert isinstance(build_calendar([2024]), ForensicCalendar)


def test_national_holidays_present():
    cal = build_calendar([2024])
    # Canonical national holidays should not be business days.
    assert not cal.is_business_day(date(2024, 9, 7))  # Independência
    assert not cal.is_business_day(date(2024, 12, 25))  # Natal
    assert not cal.is_business_day(date(2024, 5, 1))  # Trabalho


def test_ordinary_weekday_is_business_day():
    cal = build_calendar([2024])
    assert cal.is_business_day(date(2024, 9, 9))  # Monday, no holiday


def test_recess_period_applied():
    cal = build_calendar([2024])
    # Forensic recess 20/12/2024 .. 20/01/2025.
    assert not cal.is_business_day(date(2024, 12, 23))
    assert not cal.is_business_day(date(2025, 1, 2))
    assert not cal.is_business_day(date(2025, 1, 20))
    assert cal.is_business_day(date(2025, 1, 21))


def test_multiple_years():
    cal = build_calendar([2024, 2025])
    assert not cal.is_business_day(date(2025, 9, 7))  # 2025 Independência (Sunday anyway)
    assert not cal.is_business_day(date(2025, 12, 25))
