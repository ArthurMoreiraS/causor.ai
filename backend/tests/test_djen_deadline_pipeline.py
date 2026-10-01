from datetime import date

from app.agent.deadline_interpretation import DeadlineInterpretation, supported
from app.prazo_engine.calendar import ForensicCalendar
from app.prazo_engine.djen import compute_djen_civil_deadline
from app.prazo_engine.factory import build_calendar
from app.prazo_engine.legal_rules import resolve_statutory_duration


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


def _statutory(text, *, rule="cpc_1010_1", command=None, citation=None, **changes):
    return DeadlineInterpretation(**(dict(
        status="prazo", regime="cpc_civel_djen", unidade="dias_uteis",
        termo="publicacao_djen", confianca=.97, origem_duracao="regra_legal",
        regra_id=rule, comando=command or text.split(" Conforme")[0],
        citacao_normativa=citation or text.split("Conforme ")[-1],
    ) | changes))


def test_supported_statutory_rules_derive_catalog_days():
    cases = [
        ("Intime-se o apelado para apresentar contrarrazões de apelação. Conforme art. 1.010, § 1º, do CPC.",
         "cpc_1010_1", 15),
        ("Intime-se o embargado para manifestar-se sobre os embargos de declaração. Conforme art. 1.023, § 2º, do CPC.",
         "cpc_1023_2", 5),
        ("Intime-se a parte contrária para manifestar-se sobre os documentos novos juntados. Conforme art. 437, § 1º, do CPC.",
         "cpc_437_1", 15),
    ]
    for text, rule, days in cases:
        result = _statutory(text, rule=rule)
        assert supported(result, text)[0]
        assert resolve_statutory_duration(result, text).days == days


def test_statutory_rule_fails_closed_without_literal_command_and_citation():
    text = "Intime-se o apelado para apresentar contrarrazões de apelação. Conforme art. 1.010, § 1º, do CPC."
    for changed_text, changes in [
        ("Citado art. 1.010, § 1º, do CPC.", {}),
        (text.replace("contrarrazões de apelação", "razões de apelação"), {}),
        (text.replace("1.010", "1.023"), {}),
        (text, {"comando": "comando inventado"}),
        (text, {"citacao_normativa": "art. 999"}),
        (text, {"dias": 10}),
        (text + " Prazo judicial de 10 dias úteis.", {}),
        (text + " Prazo judicial de sete dias úteis.", {}),
        (text + " Prazo em dobro para a Fazenda Pública.", {}),
        (text + " Contagem da intimação pessoal.", {}),
        (text + " Também manifeste-se sobre a perícia.", {}),
        ("Transcrição da decisão anterior: " + text, {}),
        ("A parte sustenta: “" + text + "” Aguarde-se.", {}),
        ("Não " + text, {}),
        (text + " Procedimento no Juizado Especial, Lei 9.099.", {}),
        (text + " Aplica-se a CLT.", {}),
        (text + " Trata-se de processo criminal.", {}),
        (text.replace("§ 1º", "§ 2º"), {}),
        (text.replace("Conforme art. 1.010, § 1º", "Conforme art. 1.010; art. 1.023, § 1º"), {}),
    ]:
        assert not supported(_statutory(text, **changes), changed_text)[0]


def test_document_extension_and_ambiguous_parties_remain_pending():
    text = ("Intime-se a parte contrária para manifestar-se sobre os documentos novos juntados. "
            "Conforme art. 437, § 1º, do CPC. Defiro dilação do prazo nos termos do § 2º.")
    assert not supported(_statutory(text, rule="cpc_437_1"), text)[0]
    appeal = "Intime-se o apelado para apresentar contrarrazões de apelação. Conforme art. 1.010, § 1º, do CPC."
    assert not supported(_statutory(appeal, multiplas_partes=True), appeal)[0]
