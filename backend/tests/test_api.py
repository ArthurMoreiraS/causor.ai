"""TestClient TDD for the read-only API."""

from datetime import date
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.agent.classifier import ClassificacaoIntimacao
from app.api.main import create_app
from app.sor.db import get_session
from app.sor import models


@pytest.fixture
def client(db_session):
    app = create_app()
    app.dependency_overrides[get_session] = lambda: db_session
    return TestClient(app)


@pytest.fixture
def seeded(db_session):
    esc = models.Escritorio(nome="Escritório Teste")
    db_session.add(esc)
    db_session.flush()
    proc = models.Processo(escritorio_id=esc.id, numero="00000010020248260100")
    db_session.add(proc)
    db_session.flush()
    intimacao = models.Intimacao(
        processo_id=proc.id,
        fonte="DJEN",
        fonte_id="111",
        numero_processo="00000010020248260100",
        tipo_comunicacao="Intimação",
        data_disponibilizacao=date(2024, 9, 6),
        teor="Apresente contestacao em 15 dias uteis.",
    )
    db_session.add(intimacao)
    db_session.flush()
    db_session.add_all(
        [
            models.Prazo(
                processo_id=proc.id, intimacao_id=intimacao.id, descricao="A",
                data_inicio=date(2024, 9, 9), dias=15, dias_uteis=True,
                data_fatal=date(2024, 9, 30), cumprido=False,
            ),
            models.Prazo(
                processo_id=proc.id, intimacao_id=intimacao.id, descricao="B",
                data_inicio=date(2024, 9, 9), dias=5, dias_uteis=True,
                data_fatal=date(2024, 9, 16), cumprido=True,
            ),
        ]
    )
    db_session.flush()
    return proc


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_dashboard_operacional(client, seeded):
    resp = client.get("/dashboard/operational")
    assert resp.status_code == 200
    body = resp.json()
    metric_by_key = {item["key"]: item for item in body["metrics"]}
    assert metric_by_key["processos"]["value"] == 1
    assert metric_by_key["intimacoes"]["value"] == 1
    assert metric_by_key["prazos"]["value"] == 1
    assert [step["key"] for step in body["workflow"]] == [
        "capture",
        "deadline",
        "draft",
        "approval",
        "filing",
    ]
    assert {connector["key"] for connector in body["connectors"]} >= {"djen", "datajud", "pje"}


def test_listar_intimacoes(client, seeded):
    resp = client.get("/intimacoes")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["tipo_comunicacao"] == "Intimação"
    assert data[0]["numero_processo"] == "00000010020248260100"
    assert data[0]["teor"] == "Apresente contestacao em 15 dias uteis."


def test_listar_intimacoes_filter_by_processo(client, seeded):
    assert len(client.get("/intimacoes", params={"processo_id": seeded.id}).json()) == 1
    assert client.get("/intimacoes", params={"processo_id": 9999}).json() == []


def test_listar_prazos_ordered_by_data_fatal(client, seeded):
    data = client.get("/prazos").json()
    assert [p["descricao"] for p in data] == ["B", "A"]  # 09-16 before 09-30


def test_listar_prazos_filter_cumprido(client, seeded):
    pendentes = client.get("/prazos", params={"cumprido": "false"}).json()
    assert len(pendentes) == 1
    assert pendentes[0]["descricao"] == "A"


def test_fila_revisao_agrega_intimacao_prazo_e_status(client, seeded):
    data = client.get("/review/queue").json()
    assert len(data) == 1
    assert data[0]["intimacao"]["numero_processo"] == "00000010020248260100"
    assert data[0]["processo"]["id"] == seeded.id
    assert data[0]["prazo"]["descricao"] == "B"
    assert data[0]["status"] == "cumprido"
    assert data[0]["risco"] == "cumprido"


def test_revisar_prazo_atualiza_e_audita(client, db_session, seeded):
    prazo = db_session.query(models.Prazo).filter_by(descricao="A").one()
    resp = client.patch(
        f"/prazos/{prazo.id}",
        json={
            "usuario_id": 77,
            "descricao": "Manifestacao revisada",
            "dias": 10,
            "data_fatal": "2024-09-23",
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["descricao"] == "Manifestacao revisada"
    assert body["dias"] == 10
    assert body["data_fatal"] == "2024-09-23"
    audit = db_session.query(models.AuditLog).one()
    assert audit.ator == "usuario:77"
    assert audit.acao == "prazo_revisado"


def test_marcar_prazo_cumprido(client, db_session, seeded):
    prazo = db_session.query(models.Prazo).filter_by(descricao="A").one()
    resp = client.post(f"/prazos/{prazo.id}/cumprir", json={"usuario_id": 88})

    assert resp.status_code == 200
    assert resp.json()["cumprido"] is True
    audit = db_session.query(models.AuditLog).one()
    assert audit.ator == "usuario:88"
    assert audit.acao == "prazo_cumprido"


def test_listar_processos(client, seeded):
    data = client.get("/processos").json()
    assert len(data) == 1
    assert data[0]["numero"] == "00000010020248260100"


def test_listar_peticoes_and_filter_status(client, db_session, seeded):
    peticao = models.Peticao(
        processo_id=seeded.id,
        tipo="Contestacao",
        conteudo="minuta",
        status="rascunho",
    )
    db_session.add(peticao)
    db_session.flush()

    data = client.get("/peticoes", params={"status": "rascunho"}).json()
    assert len(data) == 1
    assert data[0]["tipo"] == "Contestacao"


def test_gerar_minuta_creates_prazo_and_draft(client, db_session, seeded):
    intimacao = db_session.query(models.Intimacao).one()
    classificacao = ClassificacaoIntimacao(
        tipo="Intimacao para contestar",
        peticao_sugerida="Contestacao",
        prazo_dias=15,
        dias_uteis=True,
        confianca=0.91,
        resumo="Reu intimado para contestar.",
    )

    with (
        patch("app.agent.service.classify_intimacao", return_value=classificacao),
        patch("app.agent.service.draft_peticao", return_value="MINUTA"),
    ):
        resp = client.post(
            f"/intimacoes/{intimacao.id}/draft",
            json={"calendar_years": [2024, 2025]},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["peticao"]["status"] == "rascunho"
    assert body["peticao"]["conteudo"] == "MINUTA"
    assert body["prazo"]["dias"] == 15
    assert body["classificacao"]["peticao_sugerida"] == "Contestacao"


def test_protocolar_requires_approval(client, db_session, seeded):
    peticao = models.Peticao(
        processo_id=seeded.id,
        tipo="Contestacao",
        conteudo="minuta",
        status="rascunho",
    )
    db_session.add(peticao)
    db_session.flush()

    blocked = client.post(f"/peticoes/{peticao.id}/protocolar")
    assert blocked.status_code == 409

    approved = client.post(f"/peticoes/{peticao.id}/approve", json={"usuario_id": 123})
    assert approved.status_code == 200
    assert approved.json()["status"] == "aprovada"
    assert approved.json()["aprovada_por"] == 123

    filed = client.post(f"/peticoes/{peticao.id}/protocolar")
    assert filed.status_code == 200
    assert filed.json()["status"] == "protocolada"
    assert filed.json()["protocolada_em"] is not None
