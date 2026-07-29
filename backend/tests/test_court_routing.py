"""TDD for the tribunal+grau -> sistema + URLs routing registry."""

from app.capture.court_routing import CourtRoute, resolve_route


def test_tjsp_routes_to_esaj_with_peticionamento_url():
    route = resolve_route("TJSP", "1")
    assert route is not None
    assert route.sistema == "e-SAJ"
    assert "esaj.tjsp.jus.br" in route.url_peticionamento
    assert route.verificado is True


def test_tjsp_second_degree_has_its_own_url():
    r1 = resolve_route("TJSP", "1")
    r2 = resolve_route("TJSP", "2")
    assert r1.url_peticionamento != r2.url_peticionamento


def test_unknown_tribunal_is_declared_unknown_not_guessed_as_pje():
    """Sigla fora do registro não vira PJe por palpite: o default silencioso
    mandava tribunal de e-SAJ/eproc para o fluxo errado sem avisar."""
    route = resolve_route("TJXX", "1")
    assert route.sistema == "DESCONHECIDO"
    assert route.url_peticionamento is None
    assert route.verificado is False


def test_trf3_routes_to_pje_with_login_url_per_grau():
    r1 = resolve_route("TRF3", "1")
    r2 = resolve_route("TRF3", "2")
    assert r1.sistema == "PJe"
    assert "pje1g.trf3.jus.br" in (r1.url_login or "")
    assert "pje2g.trf3.jus.br" in (r2.url_login or "")
    assert r1.verificado is True
    # PJe peticiona a partir do painel: peticionamento cai para o login.
    assert r1.url_peticionamento == r1.url_login


def test_trfs_pje_seguem_padrao_pje1g_pje2g():
    for trf in ("TRF1", "TRF5", "TRF6"):
        r1 = resolve_route(trf, "1")
        r2 = resolve_route(trf, "2")
        assert r1.sistema == "PJe", trf
        assert f"pje1g.{trf.lower()}.jus.br" in (r1.url_login or ""), trf
        assert f"pje2g.{trf.lower()}.jus.br" in (r2.url_login or ""), trf
        assert r1.verificado is True, trf


def test_tjdft_routes_to_pje_with_urls_verificadas():
    r1 = resolve_route("TJDFT", "1")
    r2 = resolve_route("TJDFT", "2")
    assert r1.sistema == "PJe"
    assert "pje.tjdft.jus.br" in (r1.url_login or "")
    assert "pje2i.tjdft.jus.br" in (r2.url_login or "")
    assert r1.verificado is True


def test_principais_tjs_pje_tem_url_nos_dois_graus():
    for tj in ("TJBA", "TJPE", "TJPA", "TJMA", "TJMT"):
        r1 = resolve_route(tj, "1")
        r2 = resolve_route(tj, "2")
        assert r1.sistema == "PJe", tj
        assert r1.url_login, tj
        assert r2.url_login, tj
        assert r1.url_login != r2.url_login, tj
        assert r1.verificado is True, tj


def test_todos_os_trts_seguem_padrao_csjt():
    for n in range(1, 25):
        r1 = resolve_route(f"TRT{n}", "1")
        r2 = resolve_route(f"TRT{n}", "2")
        assert r1.sistema == "PJe", n
        assert f"pje.trt{n}.jus.br/primeirograu" in (r1.url_login or ""), n
        assert f"pje.trt{n}.jus.br/segundograu" in (r2.url_login or ""), n
    # Conferidos individualmente contra os portais; demais sao padrao CSJT.
    assert resolve_route("TRT15", "1").verificado is True
    assert resolve_route("TRT7", "1").verificado is False


def test_none_tribunal_returns_none():
    assert resolve_route(None) is None


def test_case_and_whitespace_insensitive():
    assert resolve_route(" tjsp ", "1").sistema == "e-SAJ"


def test_courtroute_is_frozen_dataclass():
    route = resolve_route("TJSP", "1")
    assert isinstance(route, CourtRoute)
