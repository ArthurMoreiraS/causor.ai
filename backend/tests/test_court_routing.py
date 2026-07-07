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


def test_unknown_tribunal_falls_back_to_pje_without_url():
    route = resolve_route("TJXX", "1")
    assert route.sistema == "PJe"
    assert route.url_peticionamento is None
    assert route.verificado is False


def test_none_tribunal_returns_none():
    assert resolve_route(None) is None


def test_case_and_whitespace_insensitive():
    assert resolve_route(" tjsp ", "1").sistema == "e-SAJ"


def test_courtroute_is_frozen_dataclass():
    route = resolve_route("TJSP", "1")
    assert isinstance(route, CourtRoute)
