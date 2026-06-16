"""Isolamento ponta a ponta: usuário do tenant A não vê dados do B."""

import time

import jwt
import pytest
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.auth import jwt_auth
from app.sor.db import get_session
from app.sor import models

SECRET = "test-secret"


@pytest.fixture
def client(db_session, monkeypatch):
    monkeypatch.setattr(jwt_auth.settings, "supabase_jwt_secret", SECRET)
    app = create_app()
    app.dependency_overrides[get_session] = lambda: db_session
    return TestClient(app)


@pytest.fixture
def two_tenants(db_session):
    a = models.Escritorio(nome="A")
    b = models.Escritorio(nome="B")
    db_session.add_all([a, b])
    db_session.flush()
    ua = models.Usuario(escritorio_id=a.id, nome="UA", email="ua@x.com", supabase_user_id="sa")
    ub = models.Usuario(escritorio_id=b.id, nome="UB", email="ub@x.com", supabase_user_id="sb")
    db_session.add_all([ua, ub])
    db_session.flush()
    pa = models.Processo(escritorio_id=a.id, numero="A1")
    pb = models.Processo(escritorio_id=b.id, numero="B1")
    db_session.add_all([pa, pb])
    db_session.flush()
    return {"a": a, "b": b, "ua": ua, "ub": ub, "pa": pa, "pb": pb}


def _auth(sub):
    token = jwt.encode(
        {"sub": sub, "email": f"{sub}@x.com", "aud": "authenticated", "exp": int(time.time()) + 3600},
        SECRET, algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def test_health_publico(client):
    assert client.get("/health").status_code == 200


def test_sem_token_401(client, two_tenants):
    assert client.get("/processos").status_code == 401


def test_lista_so_do_proprio_tenant(client, two_tenants):
    resp = client.get("/processos", headers=_auth("sa"))
    assert resp.status_code == 200
    numeros = [p["numero"] for p in resp.json()]
    assert numeros == ["A1"]


def test_acesso_direto_a_recurso_de_outro_tenant_404(client, two_tenants):
    pb_id = two_tenants["pb"].id
    resp = client.post(f"/intimacoes/{pb_id}/draft", json={}, headers=_auth("sa"))
    assert resp.status_code in (404, 409)  # nunca 200
