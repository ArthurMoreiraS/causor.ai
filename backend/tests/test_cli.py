"""Tests for the CLI wiring (without hitting the network)."""

from datetime import date

from app.cli import _build_parser, default_calendar


def test_parser_requires_subcommand():
    parser = _build_parser()
    args = parser.parse_args(["poll", "--oab", "12345", "--uf", "SP", "--escritorio", "1"])
    assert args.command == "poll"
    assert args.oab == "12345"
    assert args.escritorio == 1
    assert args.dias == 15


def test_default_calendar_spans_three_years():
    cal = default_calendar(today=date(2024, 6, 1))
    # National holiday in the prior and next year should be recognized.
    assert not cal.is_business_day(date(2023, 12, 25))
    assert not cal.is_business_day(date(2025, 12, 25))
