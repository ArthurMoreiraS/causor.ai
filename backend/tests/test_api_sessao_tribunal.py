"""TestClient TDD for court-routing lookup + UI session capture."""

from app.api import main as api_main
from app.sor import models


def test_court_routing_endpoint_resolves_tjsp(client, seeded):
    resp = client.get("/court-routing", params={"tribunal": "TJSP", "grau": "1"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["sistema"] == "e-SAJ"
    assert "esaj.tjsp.jus.br" in body["url_peticionamento"]
    assert body["verificado"] is True


def test_court_routing_unknown_tribunal_defaults_to_pje(client, seeded):
    resp = client.get("/court-routing", params={"tribunal": "TJXX", "grau": "1"})
    assert resp.status_code == 200
    assert resp.json()["sistema"] == "PJe"


def test_capturar_sessao_stores_session_without_browser(client, db_session, seeded, monkeypatch):
    # Não abre browser de verdade no teste: injeta um storage_state fake.
    monkeypatch.setattr(
        api_main, "capture_pje_storage_state",
        lambda **kw: {"cookies": [{"name": "x", "value": "secret-cookie"}]},
    )
    usuario = db_session.query(models.Usuario).first()

    resp = client.post(
        f"/usuarios/{usuario.id}/sessoes-tribunal/capturar",
        json={"tribunal": "TJSP", "grau": "1"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["sistema"] == "e-SAJ"
    assert body["tribunal"] == "TJSP"
    assert body["grau"] == "1"
    assert body["tipo"] == "session"
    assert "secret-cookie" not in str(body)


def test_capturar_sessao_sem_url_no_registro_retorna_422(client, db_session, seeded, monkeypatch):
    monkeypatch.setattr(api_main, "capture_pje_storage_state", lambda **kw: {"cookies": []})
    usuario = db_session.query(models.Usuario).first()
    # TJMS está no registro como e-SAJ porém sem URL verificada (url_login=None).
    resp = client.post(
        f"/usuarios/{usuario.id}/sessoes-tribunal/capturar",
        json={"tribunal": "TJMS", "grau": "1"},
    )
    assert resp.status_code == 422
