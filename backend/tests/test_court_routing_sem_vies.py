"""PJe não pode ser o palpite silencioso para tribunal desconhecido."""

from app.capture.court_routing import resolve_route


def test_tribunal_desconhecido_nao_vira_pje():
    route = resolve_route("TJXX", "1")
    assert route is not None
    assert route.sistema == "DESCONHECIDO"
    assert route.verificado is False


def test_tribunal_conhecido_mantem_o_sistema():
    assert resolve_route("TJTO", "1").sistema == "EPROC"
    assert resolve_route("TJSP", "1").sistema == "e-SAJ"
    assert resolve_route("TJMG", "1").sistema == "PJe"


def test_tjto_tem_url_de_login_para_os_dois_graus():
    for grau in ("1", "2"):
        route = resolve_route("TJTO", grau)
        assert route.url_login, f"TJTO grau {grau} sem url_login"
        assert route.url_login.startswith("https://eproc")
        assert route.verificado is True
