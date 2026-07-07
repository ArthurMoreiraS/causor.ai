"""TDD for the deterministic tribunal -> processing-system inference."""

from app.capture.court_systems import sistema_para_tribunal


def test_pje_is_the_default_for_federal_and_labor():
    # Justiça Federal e do Trabalho são PJe — o caminho automatizável.
    assert sistema_para_tribunal("TRF3") == "PJe"
    assert sistema_para_tribunal("TRT2") == "PJe"
    assert sistema_para_tribunal("TST") == "PJe"


def test_pje_is_the_default_for_unknown_tribunais():
    # Maioria dos TJs roda PJe; siglas não mapeadas caem no default PJe.
    assert sistema_para_tribunal("TJMG") == "PJe"
    assert sistema_para_tribunal("TJXX") == "PJe"


def test_esaj_courts():
    assert sistema_para_tribunal("TJSP") == "e-SAJ"
    assert sistema_para_tribunal("TJMS") == "e-SAJ"


def test_eproc_courts():
    assert sistema_para_tribunal("TJRS") == "EPROC"
    assert sistema_para_tribunal("TRF4") == "EPROC"


def test_projudi_courts():
    assert sistema_para_tribunal("TJPR") == "Projudi"


def test_case_and_whitespace_insensitive():
    assert sistema_para_tribunal(" tjsp ") == "e-SAJ"


def test_none_or_empty_returns_none():
    assert sistema_para_tribunal(None) is None
    assert sistema_para_tribunal("") is None
