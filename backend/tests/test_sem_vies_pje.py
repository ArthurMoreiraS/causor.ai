"""PJe não pode ser o palpite silencioso para tribunal desconhecido."""

import pytest

from app.capture.court_routing import resolve_route
from app.connectors.pje.session import PjeSessionError, validate_training_base_url


def test_tribunal_desconhecido_nao_vira_pje():
    route = resolve_route("TJXX", "1")
    assert route is not None
    assert route.sistema == "DESCONHECIDO"
    assert route.verificado is False


def test_tribunal_conhecido_mantem_o_sistema():
    assert resolve_route("TJTO", "1").sistema == "EPROC"
    assert resolve_route("TJSP", "1").sistema == "e-SAJ"
    assert resolve_route("TJMG", "1").sistema == "PJe"


def test_producao_bloqueada_para_eproc_tambem(monkeypatch):
    """Antes só o PJe tinha trava: eproc/e-SAJ/Projudi abriam portal de
    produção sem nenhuma barreira."""
    monkeypatch.delenv("CAUSOR_COURT_ALLOW_PROD", raising=False)
    monkeypatch.delenv("CAUSOR_PJE_ALLOW_PROD", raising=False)
    with pytest.raises(PjeSessionError):
        validate_training_base_url("https://eproc1.tjto.jus.br/eprocV2_prod_1grau/")


def test_homologacao_continua_liberada(monkeypatch):
    monkeypatch.delenv("CAUSOR_COURT_ALLOW_PROD", raising=False)
    monkeypatch.delenv("CAUSOR_PJE_ALLOW_PROD", raising=False)
    validate_training_base_url("https://pje-homolog.tjxx.jus.br/pje/")


def test_flag_nova_libera(monkeypatch):
    # A flag antiga precisa sair: o .env de dev traz CAUSOR_PJE_ALLOW_PROD=1 e
    # o teste passaria sem exercitar a flag nova.
    monkeypatch.delenv("CAUSOR_PJE_ALLOW_PROD", raising=False)
    monkeypatch.setenv("CAUSOR_COURT_ALLOW_PROD", "1")
    validate_training_base_url("https://eproc1.tjto.jus.br/eprocV2_prod_1grau/")


def test_flag_antiga_continua_valendo(monkeypatch):
    """Compatibilidade: o .env de quem já rodava não pode quebrar."""
    monkeypatch.delenv("CAUSOR_COURT_ALLOW_PROD", raising=False)
    monkeypatch.setenv("CAUSOR_PJE_ALLOW_PROD", "1")
    validate_training_base_url("https://eproc1.tjto.jus.br/eprocV2_prod_1grau/")


def test_assistant_nao_chuta_pje_para_processo_sem_sistema():
    from app.connectors.assistant import route_for

    class ProcessoFake:
        tribunal = "TJXX"
        sistema = None

    assert route_for(ProcessoFake(), "1")["sistema"] == "DESCONHECIDO"


def test_tjto_tem_url_de_login_para_os_dois_graus():
    """Sem URL no registro, /conectores/login devolve 422 e o agente nunca
    chega a abrir o navegador — a validacao live ficava bloqueada."""
    for grau in ("1", "2"):
        route = resolve_route("TJTO", grau)
        assert route.url_login, f"TJTO grau {grau} sem url_login"
        assert route.url_login.startswith("https://eproc")
        assert route.verificado is True
