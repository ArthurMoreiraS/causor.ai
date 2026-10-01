from datetime import date

from app.agent.deadline_interpretation import DeadlineInterpretation, supported
from app.prazo_engine.calendar import ForensicCalendar
from app.prazo_engine.djen import compute_djen_civil_deadline
from app.prazo_engine.factory import build_calendar


def _calendars(years=range(2024, 2028)):
    counting = build_calendar(years)
    return ForensicCalendar(holidays=counting._holidays), counting


def test_friday_publication_monday_counting_tuesday():
    publication, counting = _calendars()
    result = compute_djen_civil_deadline(date(2026, 9, 25), 1,
        publication_calendar=publication, counting_calendar=counting)
    assert (result.publicacao, result.primeiro_dia, result.data_fatal) == (
        date(2026, 9, 28), date(2026, 9, 29), date(2026, 9, 29))


def test_publication_during_recess_and_counting_after_recess():
    publication, counting = _calendars()
    result = compute_djen_civil_deadline(date(2026, 12, 21), 1,
        publication_calendar=publication, counting_calendar=counting)
    assert result.publicacao == date(2026, 12, 22)
    assert result.primeiro_dia == date(2027, 1, 21)


def test_explicit_publication_does_not_shift_at_confirmation():
    publication, counting = _calendars()
    result = compute_djen_civil_deadline(date(2026, 12, 21), 1,
        publication_calendar=publication, counting_calendar=counting,
        publication=date(2026, 12, 22))
    assert result.publicacao == date(2026, 12, 22)
    assert result.data_fatal == date(2027, 1, 21)


def test_national_november_20_since_2024():
    assert build_calendar([2023]).is_business_day(date(2023, 11, 20))
    assert not build_calendar([2024]).is_business_day(date(2024, 11, 20))


def test_duration_must_match_exact_evidence():
    result = DeadlineInterpretation(status="prazo", regime="cpc_civel_djen",
        dias=15, unidade="dias_uteis", termo="publicacao_djen",
        evidencia="prazo de 5 dias úteis", confianca=.98)
    assert not supported(result, "prazo de 5 dias úteis")[0]


def test_interpretation_fail_closed_for_unsupported_or_ambiguous_cases():
    base = dict(status="prazo", regime="cpc_civel_djen", dias=5, unidade="dias_uteis",
                termo="publicacao_djen", evidencia="manifestar em 5 dias úteis", confianca=.96)
    text = "manifestar em 5 dias úteis"
    for changes in ({"dias": None}, {"confianca": .5}, {"regime": "outro"},
                    {"unidade": "dias_corridos"}, {"termo": "outro"},
                    {"multiplos_atos": True}, {"multiplas_partes": True},
                    {"evidencia": "trecho inexistente"}):
        assert not supported(DeadlineInterpretation(**(base | changes)), text)[0]


def test_explicit_holiday_delays_count_not_publication():
    publication, _ = _calendars()
    counting = build_calendar(range(2025, 2028), extra_holidays=[date(2026, 9, 29)])
    result = compute_djen_civil_deadline(date(2026, 9, 25), 1,
        publication_calendar=publication, counting_calendar=counting)
    assert result.publicacao == date(2026, 9, 28)
    assert result.primeiro_dia == result.data_fatal == date(2026, 9, 30)
