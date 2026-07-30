"""TDD for the deterministic tribunal -> processing-system inference."""

from app.capture.court_systems import sistema_para_tribunal


def test_federal_labor_and_electoral_are_registered_as_pje():
    """Justiça Federal, do Trabalho e Eleitoral são PJe — e agora por entrada
    explícita no registro, não por default silencioso."""
    assert sistema_para_tribunal("TRF3") == "PJe"
    assert sistema_para_tribunal("TRT2") == "PJe"
    assert sistema_para_tribunal("TST") == "PJe"
    assert sistema_para_tribunal("TSE") == "PJe"
    assert sistema_para_tribunal("TRE-SP") == "PJe"
    assert sistema_para_tribunal("TRESP") == "PJe"


def test_state_courts_in_pje_are_registered_explicitly():
    assert sistema_para_tribunal("TJMG") == "PJe"
    assert sistema_para_tribunal("TJRJ") == "PJe"
    assert sistema_para_tribunal("TJRR") == "PJe"


def test_unknown_sigla_is_declared_unknown():
    """Sem palpite: sigla que ninguém mapeou é declaradamente desconhecida."""
    assert sistema_para_tribunal("TJXX") == "DESCONHECIDO"


def test_trf2_is_eproc_not_the_old_pje_guess():
    """O default antigo classificava o TRF2 como PJe, e ele é eproc."""
    assert sistema_para_tribunal("TRF2") == "EPROC"


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


def test_tribunais_superiores_com_sistema_proprio():
    """STJ e STF nao usam PJe: cada um tem sistema proprio de peticionamento.

    Sem entrada no registro eles caiam em DESCONHECIDO e o backfill deixava
    `processo.sistema` nulo, o que a tela mostrava como "Nao identificado" —
    lido como bug, quando o correto e informar o sistema real do tribunal.
    Nenhum dos dois tem conector no Causor; o driver de protocolo segue
    falhando fechado para eles.
    """
    assert sistema_para_tribunal("STJ") == "e-STJ"
    assert sistema_para_tribunal("STF") == "STF Digital"
    # Os superiores que realmente rodam PJe continuam PJe.
    assert sistema_para_tribunal("TST") == "PJe"
    assert sistema_para_tribunal("TSE") == "PJe"
