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


def test_alertas_derivados_dos_prazos(client, db_session, seeded):
    from datetime import date, timedelta

    today = date.today()
    proc = seeded
    db_session.add_all(
        [
            models.Prazo(
                processo_id=proc.id, descricao="Vencido", data_inicio=today - timedelta(days=20),
                dias=15, dias_uteis=True, data_fatal=today - timedelta(days=2), cumprido=False,
            ),
            models.Prazo(
                processo_id=proc.id, descricao="Hoje", data_inicio=today - timedelta(days=15),
                dias=15, dias_uteis=True, data_fatal=today, cumprido=False,
            ),
            models.Prazo(
                processo_id=proc.id, descricao="Amanha", data_inicio=today - timedelta(days=14),
                dias=15, dias_uteis=True, data_fatal=today + timedelta(days=1), cumprido=False,
            ),
            models.Prazo(
                processo_id=proc.id, descricao="D3", data_inicio=today - timedelta(days=12),
                dias=15, dias_uteis=True, data_fatal=today + timedelta(days=3), cumprido=False,
            ),
            models.Prazo(
                processo_id=proc.id, descricao="Longe", data_inicio=today,
                dias=15, dias_uteis=True, data_fatal=today + timedelta(days=10), cumprido=False,
            ),
            models.Prazo(
                processo_id=proc.id, descricao="CumpridoHoje", data_inicio=today - timedelta(days=15),
                dias=15, dias_uteis=True, data_fatal=today, cumprido=True,
            ),
        ]
    )
    db_session.flush()

    resp = client.get("/alertas")

    assert resp.status_code == 200
    body = resp.json()
    por_descricao = {a["descricao"]: a for a in body}
    # Prazos confortáveis e cumpridos ficam fora; "A" (da fixture) está vencido e aberto.
    assert set(por_descricao) == {"A", "Vencido", "Hoje", "Amanha", "D3"}
    assert por_descricao["A"]["nivel"] == "vencido"
    assert por_descricao["Vencido"]["nivel"] == "vencido"
    assert por_descricao["Hoje"]["nivel"] == "d0"
    assert por_descricao["Amanha"]["nivel"] == "d1"
    assert por_descricao["D3"]["nivel"] == "d3"
    assert por_descricao["Hoje"]["processo_numero"] == proc.numero
    # Ordenação: mais crítico primeiro; vencidos do mais antigo ao mais recente.
    assert [a["nivel"] for a in body] == ["vencido", "vencido", "d0", "d1", "d3"]
    assert [a["descricao"] for a in body[:2]] == ["A", "Vencido"]


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


def test_gerar_minuta_audita(client, db_session, seeded):
    intimacao = db_session.query(models.Intimacao).one()
    classificacao = ClassificacaoIntimacao(
        tipo="Intimacao para contestar",
        peticao_sugerida="Contestacao",
        prazo_dias=15,
        dias_uteis=True,
        confianca=0.9,
        resumo="Reu intimado.",
    )
    with (
        patch("app.agent.service.classify_intimacao", return_value=classificacao),
        patch("app.agent.service.draft_peticao", return_value="MINUTA"),
    ):
        resp = client.post(f"/intimacoes/{intimacao.id}/draft", json={})

    assert resp.status_code == 200
    audit = db_session.query(models.AuditLog).filter_by(acao="minuta_gerada").one()
    assert audit.entidade == "peticao"
    assert audit.entidade_id == resp.json()["peticao"]["id"]


def test_gerar_minuta_falha_de_ia_retorna_503(client, db_session, seeded):
    intimacao = db_session.query(models.Intimacao).one()
    with patch(
        "app.api.main.draft_from_intimacao",
        side_effect=RuntimeError("anthropic indisponivel"),
    ):
        resp = client.post(f"/intimacoes/{intimacao.id}/draft", json={})

    assert resp.status_code == 503
    assert "minuta" in resp.json()["detail"].lower()


def test_aprovar_peticao_audita(client, db_session, seeded):
    peticao = models.Peticao(
        processo_id=seeded.id, tipo="Contestacao", conteudo="m", status="rascunho"
    )
    db_session.add(peticao)
    db_session.flush()

    resp = client.post(f"/peticoes/{peticao.id}/approve", json={"usuario_id": 55})

    assert resp.status_code == 200
    audit = db_session.query(models.AuditLog).filter_by(acao="peticao_aprovada").one()
    assert audit.ator == "usuario:55"
    assert audit.entidade_id == peticao.id


def test_editar_peticao_atualiza_conteudo_e_audita(client, db_session, seeded):
    peticao = models.Peticao(
        processo_id=seeded.id, tipo="Contestacao", conteudo="rascunho inicial", status="rascunho"
    )
    db_session.add(peticao)
    db_session.flush()

    resp = client.patch(
        f"/peticoes/{peticao.id}",
        json={"conteudo": "texto revisado", "usuario_id": 7},
    )

    assert resp.status_code == 200
    assert resp.json()["conteudo"] == "texto revisado"
    audit = db_session.query(models.AuditLog).filter_by(acao="peticao_editada").one()
    assert audit.ator == "usuario:7"
    assert audit.entidade_id == peticao.id


def test_editar_peticao_permite_transicao_para_revisao(client, db_session, seeded):
    peticao = models.Peticao(
        processo_id=seeded.id, tipo="Contestacao", conteudo="m", status="rascunho"
    )
    db_session.add(peticao)
    db_session.flush()

    resp = client.patch(
        f"/peticoes/{peticao.id}",
        json={"status": "em_revisao", "usuario_id": 7},
    )

    assert resp.status_code == 200
    assert resp.json()["status"] == "em_revisao"


def test_editar_peticao_rejeita_status_de_gate(client, db_session, seeded):
    peticao = models.Peticao(
        processo_id=seeded.id, tipo="Contestacao", conteudo="m", status="rascunho"
    )
    db_session.add(peticao)
    db_session.flush()

    # aprovada/protocolada têm endpoints próprios (gate humano); PATCH não atalha.
    resp = client.patch(
        f"/peticoes/{peticao.id}",
        json={"status": "aprovada", "usuario_id": 7},
    )
    assert resp.status_code == 422


def test_editar_peticao_protocolada_retorna_409(client, db_session, seeded):
    peticao = models.Peticao(
        processo_id=seeded.id,
        tipo="Contestacao",
        conteudo="m",
        status="protocolada",
        aprovada_por=1,
    )
    db_session.add(peticao)
    db_session.flush()

    resp = client.patch(
        f"/peticoes/{peticao.id}",
        json={"conteudo": "alterando depois do protocolo", "usuario_id": 7},
    )
    assert resp.status_code == 409


def test_editar_peticao_inexistente_retorna_404(client):
    resp = client.patch("/peticoes/9999", json={"conteudo": "x", "usuario_id": 7})
    assert resp.status_code == 404


def test_protocolar_peticao_audita(client, db_session, seeded):
    peticao = models.Peticao(
        processo_id=seeded.id,
        tipo="Contestacao",
        conteudo="m",
        status="aprovada",
        aprovada_por=1,
    )
    db_session.add(peticao)
    db_session.flush()

    resp = client.post(f"/peticoes/{peticao.id}/protocolar")

    assert resp.status_code == 200
    audit = db_session.query(models.AuditLog).filter_by(acao="peticao_protocolada").one()
    assert audit.entidade_id == peticao.id


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


def test_chat_retorna_reply_e_propostas(client, db_session, seeded, monkeypatch):
    def fake_chat(messages, *, session, **kwargs):
        return {
            "reply": "Você tem 1 prazo pendente; quer gerar a minuta?",
            "proposed_actions": [
                {
                    "tipo": "gerar_minuta",
                    "label": "Gerar minuta",
                    "endpoint": "/intimacoes/1/draft",
                    "metodo": "POST",
                    "payload": {"intimacao_id": 1},
                }
            ],
            "tool_trace": [{"ferramenta": "listar_prazos", "input": {}}],
        }

    monkeypatch.setattr("app.api.main.chat_with_assistant", fake_chat)
    resp = client.post("/chat", json={"messages": [{"role": "user", "content": "meus prazos?"}]})

    assert resp.status_code == 200
    body = resp.json()
    assert "prazo" in body["reply"].lower()
    assert body["proposed_actions"][0]["tipo"] == "gerar_minuta"
    assert body["tool_trace"][0]["ferramenta"] == "listar_prazos"


def test_chat_falha_de_ia_retorna_503(client, db_session, seeded, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("anthropic indisponivel")

    monkeypatch.setattr("app.api.main.chat_with_assistant", boom)
    resp = client.post("/chat", json={"messages": [{"role": "user", "content": "oi"}]})
    assert resp.status_code == 503
    assert "assistente" in resp.json()["detail"].lower()


def test_listar_auditoria_filtra_por_entidade(client, db_session, seeded):
    db_session.add_all(
        [
            models.AuditLog(ator="usuario:1", acao="prazo_revisado", entidade="prazo", entidade_id=1),
            models.AuditLog(ator="system", acao="captura_oab_executada", entidade="escritorio", entidade_id=1),
        ]
    )
    db_session.flush()

    todos = client.get("/audit").json()
    assert len(todos) == 2
    # mais recente primeiro
    assert todos[0]["acao"] in {"prazo_revisado", "captura_oab_executada"}

    so_prazo = client.get("/audit", params={"entidade": "prazo"}).json()
    assert len(so_prazo) == 1
    assert so_prazo[0]["entidade"] == "prazo"
    assert so_prazo[0]["ator"] == "usuario:1"


def test_criar_e_consultar_job_captura_oab(client, db_session, seeded):
    resp = client.post(
        "/jobs/capture/oab",
        json={
            "oab": "123456",
            "uf": "SP",
            "escritorio_id": seeded.escritorio_id,
            "dias_default": 15,
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["tipo"] == "captura_oab"
    assert body["status"] == "queued"
    assert body["entidade"] == "escritorio"
    assert body["entidade_id"] == seeded.escritorio_id
    assert body["payload"]["oab"] == "123456"

    fetched = client.get(f"/jobs/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == body["id"]

    audit = db_session.query(models.AuditLog).filter_by(acao="job_criado").one()
    assert audit.entidade == "job_execucao"
    assert audit.entidade_id == body["id"]


def test_consultar_job_inexistente_retorna_404(client, seeded):
    resp = client.get("/jobs/999999")
    assert resp.status_code == 404


def test_protocolar_async_exige_aprovacao(client, db_session, seeded):
    peticao = models.Peticao(
        processo_id=seeded.id,
        tipo="Contestacao",
        conteudo="minuta",
        status="rascunho",
    )
    db_session.add(peticao)
    db_session.flush()

    resp = client.post(f"/peticoes/{peticao.id}/protocolar/async")

    assert resp.status_code == 409
    assert db_session.query(models.JobExecucao).count() == 0


def test_protocolar_async_cria_job_concluido_e_audita(client, db_session, seeded):
    peticao = models.Peticao(
        processo_id=seeded.id,
        tipo="Contestacao",
        conteudo="minuta",
        status="aprovada",
        aprovada_por=7,
    )
    db_session.add(peticao)
    db_session.flush()

    resp = client.post(f"/peticoes/{peticao.id}/protocolar/async")

    assert resp.status_code == 200
    body = resp.json()
    assert body["tipo"] == "protocolo_peticao"
    assert body["status"] == "completed"
    assert body["entidade"] == "peticao"
    assert body["entidade_id"] == peticao.id
    assert body["resultado"]["peticao_id"] == peticao.id
    assert body["resultado"]["protocolo"].startswith("FAKE-")

    db_session.refresh(peticao)
    assert peticao.status == "protocolada"
    assert peticao.protocolada_em is not None

    actions = {row.acao for row in db_session.query(models.AuditLog).all()}
    assert {"job_criado", "job_iniciado", "job_concluido", "peticao_protocolada"} <= actions


def test_listar_usuarios_por_escritorio(client, db_session, seeded):
    db_session.add_all(
        [
            models.Usuario(
                escritorio_id=seeded.escritorio_id,
                nome="Dra. Helena",
                email="helena@example.com",
                oab="111111",
                oab_uf="SP",
            ),
            models.Usuario(
                escritorio_id=seeded.escritorio_id,
                nome="Rafael",
                email="rafael@example.com",
                oab="222222",
                oab_uf="SP",
            ),
        ]
    )
    db_session.flush()

    resp = client.get("/usuarios")
    assert resp.status_code == 200
    body = resp.json()
    assert [u["nome"] for u in body] == ["Dra. Helena", "Rafael"]
    assert body[0]["escritorio_id"] == seeded.escritorio_id

    filtrado = client.get("/usuarios", params={"escritorio_id": 9999}).json()
    assert filtrado == []


def test_listar_jobs_mais_recentes_primeiro_com_filtros(client, db_session, seeded):
    peticao = models.Peticao(
        processo_id=seeded.id,
        tipo="Contestacao",
        conteudo="minuta",
        status="aprovada",
        aprovada_por=7,
    )
    db_session.add(peticao)
    db_session.flush()

    capture = client.post(
        "/jobs/capture/oab",
        json={"oab": "123456", "uf": "SP", "escritorio_id": seeded.escritorio_id},
    ).json()
    protocolo = client.post(f"/peticoes/{peticao.id}/protocolar/async").json()

    todos = client.get("/jobs").json()
    assert [job["id"] for job in todos] == [protocolo["id"], capture["id"]]

    so_protocolo = client.get("/jobs", params={"tipo": "protocolo_peticao"}).json()
    assert [job["id"] for job in so_protocolo] == [protocolo["id"]]
    assert so_protocolo[0]["status"] == "completed"
    assert so_protocolo[0]["resultado"]["protocolo"].startswith("FAKE-")

    so_queued = client.get("/jobs", params={"status": "queued"}).json()
    assert [job["id"] for job in so_queued] == [capture["id"]]


def _usuario_com_credencial(client, db_session, escritorio_id):
    usuario = models.Usuario(
        escritorio_id=escritorio_id,
        nome="Advogada Teste",
        email="advogada@example.com",
        oab="123456",
        oab_uf="SP",
    )
    db_session.add(usuario)
    db_session.flush()
    credencial = client.post(
        f"/usuarios/{usuario.id}/credenciais-assinatura",
        json={"provedor": "BirdID", "referencia_externa": "birdid-account-123"},
    ).json()
    return usuario, credencial


def test_protocolar_async_com_credencial_registra_payload_e_audita(client, db_session, seeded):
    usuario, credencial = _usuario_com_credencial(client, db_session, seeded.escritorio_id)
    peticao = models.Peticao(
        processo_id=seeded.id,
        tipo="Contestacao",
        conteudo="minuta",
        status="aprovada",
        aprovada_por=usuario.id,
    )
    db_session.add(peticao)
    db_session.flush()

    resp = client.post(
        f"/peticoes/{peticao.id}/protocolar/async",
        json={"credencial_id": credencial["id"]},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"
    assert body["payload"]["credencial_id"] == credencial["id"]
    # segredo/referência externa nunca aparece no job nem na auditoria
    assert "birdid-account-123" not in str(body)

    audit = db_session.query(models.AuditLog).filter_by(acao="peticao_protocolada").one()
    assert audit.detalhe["credencial_id"] == credencial["id"]
    assert "birdid-account-123" not in str(audit.detalhe)


def test_protocolar_async_com_credencial_inexistente_retorna_404(client, db_session, seeded):
    peticao = models.Peticao(
        processo_id=seeded.id,
        tipo="Contestacao",
        conteudo="minuta",
        status="aprovada",
        aprovada_por=7,
    )
    db_session.add(peticao)
    db_session.flush()

    resp = client.post(
        f"/peticoes/{peticao.id}/protocolar/async",
        json={"credencial_id": 999999},
    )

    assert resp.status_code == 404
    db_session.refresh(peticao)
    assert peticao.status == "aprovada"


def test_protocolar_async_com_credencial_inativa_retorna_409(client, db_session, seeded):
    usuario, credencial = _usuario_com_credencial(client, db_session, seeded.escritorio_id)
    client.patch(f"/credenciais-assinatura/{credencial['id']}/desativar")
    peticao = models.Peticao(
        processo_id=seeded.id,
        tipo="Contestacao",
        conteudo="minuta",
        status="aprovada",
        aprovada_por=usuario.id,
    )
    db_session.add(peticao)
    db_session.flush()

    resp = client.post(
        f"/peticoes/{peticao.id}/protocolar/async",
        json={"credencial_id": credencial["id"]},
    )

    assert resp.status_code == 409
    db_session.refresh(peticao)
    assert peticao.status == "aprovada"


def test_cadastrar_listar_e_desativar_credencial_assinatura(client, db_session, seeded):
    usuario = models.Usuario(
        escritorio_id=seeded.escritorio_id,
        nome="Advogada Teste",
        email="advogada@example.com",
        oab="123456",
        oab_uf="SP",
    )
    db_session.add(usuario)
    db_session.flush()

    resp = client.post(
        f"/usuarios/{usuario.id}/credenciais-assinatura",
        json={"provedor": "BirdID", "referencia_externa": "birdid-account-123"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["usuario_id"] == usuario.id
    assert body["provedor"] == "BirdID"
    assert body["ativo"] is True
    assert body["referencia_vault"].startswith("localdev://assinatura/")
    assert "birdid-account-123" not in body["referencia_vault"]
    assert "referencia_externa" not in body

    listed = client.get(f"/usuarios/{usuario.id}/credenciais-assinatura")
    assert listed.status_code == 200
    assert listed.json()[0]["id"] == body["id"]

    disabled = client.patch(f"/credenciais-assinatura/{body['id']}/desativar")
    assert disabled.status_code == 200
    assert disabled.json()["ativo"] is False

    audit_details = [row.detalhe for row in db_session.query(models.AuditLog).all()]
    assert all("birdid-account-123" not in str(detail) for detail in audit_details)


def test_credencial_assinatura_rejeita_campo_de_segredo(client, db_session, seeded):
    usuario = models.Usuario(
        escritorio_id=seeded.escritorio_id,
        nome="Advogado Teste",
        email="advogado@example.com",
    )
    db_session.add(usuario)
    db_session.flush()

    resp = client.post(
        f"/usuarios/{usuario.id}/credenciais-assinatura",
        json={
            "provedor": "A1",
            "referencia_externa": "provider-ref",
            "senha_pfx": "nao-pode-vazar",
        },
    )

    assert resp.status_code == 422
    assert db_session.query(models.CredencialAssinatura).count() == 0


def test_cadastrar_credencial_usuario_inexistente_retorna_404(client, seeded):
    resp = client.post(
        "/usuarios/999999/credenciais-assinatura",
        json={"provedor": "BirdID", "referencia_externa": "provider-ref"},
    )

    assert resp.status_code == 404


def test_criar_listar_e_atualizar_template_peticao(client, db_session, seeded):
    resp = client.post(
        f"/escritorios/{seeded.escritorio_id}/templates-peticao",
        json={
            "tipo": "Contestacao",
            "area": "civel",
            "nome": "Contestacao padrao",
            "conteudo": "Modelo com fatos, fundamentos e pedidos.",
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["escritorio_id"] == seeded.escritorio_id
    assert body["tipo"] == "Contestacao"
    assert body["ativo"] is True

    listed = client.get(
        f"/escritorios/{seeded.escritorio_id}/templates-peticao",
        params={"ativo": "true", "tipo": "Contestacao"},
    )
    assert listed.status_code == 200
    assert listed.json()[0]["id"] == body["id"]

    patched = client.patch(
        f"/templates-peticao/{body['id']}",
        json={"nome": "Contestacao revisada", "ativo": False},
    )
    assert patched.status_code == 200
    assert patched.json()["nome"] == "Contestacao revisada"
    assert patched.json()["ativo"] is False

    actions = {row.acao for row in db_session.query(models.AuditLog).all()}
    assert {"template_peticao_criado", "template_peticao_atualizado"} <= actions


def test_criar_template_escritorio_inexistente_retorna_404(client, seeded):
    resp = client.post(
        "/escritorios/999999/templates-peticao",
        json={
            "tipo": "Contestacao",
            "nome": "Contestacao padrao",
            "conteudo": "Modelo com fatos, fundamentos e pedidos.",
        },
    )

    assert resp.status_code == 404


def test_registrar_e_listar_oab_monitorada(client, db_session):
    esc = models.Escritorio(nome="Escritório Teste")
    db_session.add(esc)
    db_session.flush()

    resp = client.post(
        "/capturas/oab",
        json={"escritorio_id": esc.id, "oab": "12345", "uf": "SP", "intervalo_horas": 6},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["oab"] == "12345"
    assert body["ativo"] is True
    assert body["intervalo_horas"] == 6

    listed = client.get("/capturas/oab")
    assert listed.status_code == 200
    assert any(o["oab"] == "12345" for o in listed.json())


def test_registrar_oab_idempotente_reativa(client, db_session):
    esc = models.Escritorio(nome="Escritório Teste")
    db_session.add(esc)
    db_session.flush()

    first = client.post("/capturas/oab", json={"escritorio_id": esc.id, "oab": "999", "uf": "RJ"})
    second = client.post("/capturas/oab", json={"escritorio_id": esc.id, "oab": "999", "uf": "RJ"})
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert db_session.query(models.OabMonitorada).count() == 1
