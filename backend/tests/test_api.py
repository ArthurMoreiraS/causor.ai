"""TestClient TDD for the read-only API."""

from datetime import date
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.agent.classifier import ClassificacaoIntimacao
from app.api.main import create_app
from app.auth.jwt_auth import CurrentUser, get_current_user
from app.sor.db import get_session
from app.sor import models
from sqlalchemy import select


@pytest.fixture
def client(db_session):
    app = create_app()
    app.dependency_overrides[get_session] = lambda: db_session

    def _current_user() -> CurrentUser:
        # Resolve a identidade da fixture `seeded` (primeiro escritório/usuário do
        # tenant semeado) em tempo de request, evitando JWT real nos testes de API.
        esc = db_session.scalars(
            select(models.Escritorio).order_by(models.Escritorio.id)
        ).first()
        usuario = (
            db_session.scalars(
                select(models.Usuario)
                .where(models.Usuario.escritorio_id == esc.id)
                .order_by(models.Usuario.id)
            ).first()
            if esc is not None
            else None
        )
        return CurrentUser(
            usuario_id=usuario.id if usuario is not None else 0,
            escritorio_id=esc.id if esc is not None else 0,
            email=usuario.email if usuario is not None else "test@x.com",
        )

    app.dependency_overrides[get_current_user] = _current_user
    return TestClient(app)


@pytest.fixture
def seeded(db_session):
    esc = models.Escritorio(nome="Escritório Teste")
    db_session.add(esc)
    db_session.flush()
    usuario = models.Usuario(
        escritorio_id=esc.id, nome="Adv Seed", email="seed@example.com",
        supabase_user_id="seed-sub",
    )
    db_session.add(usuario)
    db_session.flush()
    proc = models.Processo(escritorio_id=esc.id, numero="00000010020248260100")
    db_session.add(proc)
    db_session.flush()
    intimacao = models.Intimacao(
        processo_id=proc.id,
        escritorio_id=esc.id,
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
                processo_id=proc.id, intimacao_id=intimacao.id, escritorio_id=esc.id,
                descricao="A",
                data_inicio=date(2024, 9, 9), dias=15, dias_uteis=True,
                data_fatal=date(2024, 9, 30), cumprido=False,
            ),
            models.Prazo(
                processo_id=proc.id, intimacao_id=intimacao.id, escritorio_id=esc.id,
                descricao="B",
                data_inicio=date(2024, 9, 9), dias=5, dias_uteis=True,
                data_fatal=date(2024, 9, 16), cumprido=True,
            ),
        ]
    )
    db_session.flush()
    return proc


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_me_retorna_usuario_e_tenant_autenticados(client, db_session, seeded):
    usuario = db_session.scalar(
        select(models.Usuario).where(models.Usuario.escritorio_id == seeded.escritorio_id)
    )

    resp = client.get("/me")

    assert resp.status_code == 200
    assert resp.json() == {
        "usuario_id": usuario.id,
        "escritorio_id": seeded.escritorio_id,
        "email": "seed@example.com",
    }


def test_settings_profile_retorna_usuario_e_escritorio(client, db_session, seeded):
    resp = client.get("/settings/profile")

    assert resp.status_code == 200
    body = resp.json()
    assert body["usuario"]["email"] == "seed@example.com"
    assert body["usuario"]["nome"] == "Adv Seed"
    assert body["escritorio"]["id"] == seeded.escritorio_id
    assert body["escritorio"]["nome"] == "Escritório Teste"


def test_settings_profile_atualiza_usuario_e_escritorio(client, db_session, seeded):
    resp = client.patch(
        "/settings/profile",
        json={
            "nome_usuario": "Arthur Moreira",
            "nome_escritorio": "Causor Advocacia",
            "cnpj": "12345678000190",
            "oab": "206575",
            "oab_uf": "sp",
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["usuario"]["nome"] == "Arthur Moreira"
    assert body["usuario"]["oab"] == "206575"
    assert body["usuario"]["oab_uf"] == "SP"
    assert body["escritorio"]["nome"] == "Causor Advocacia"
    assert body["escritorio"]["cnpj"] == "12345678000190"

    usuario = db_session.get(models.Usuario, body["usuario"]["id"])
    escritorio = db_session.get(models.Escritorio, body["escritorio"]["id"])
    assert usuario.nome == "Arthur Moreira"
    assert escritorio.nome == "Causor Advocacia"
    assert db_session.query(models.AuditLog).filter_by(
        acao="perfil_operacional_atualizado"
    ).count() == 1


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
    seed_user = db_session.query(models.Usuario).first()
    audit = db_session.query(models.AuditLog).one()
    assert audit.ator == f"usuario:{seed_user.id}"
    assert audit.acao == "prazo_revisado"


def test_marcar_prazo_cumprido(client, db_session, seeded):
    prazo = db_session.query(models.Prazo).filter_by(descricao="A").one()
    resp = client.post(f"/prazos/{prazo.id}/cumprir")

    assert resp.status_code == 200
    assert resp.json()["cumprido"] is True
    seed_user = db_session.query(models.Usuario).first()
    audit = db_session.query(models.AuditLog).one()
    assert audit.ator == f"usuario:{seed_user.id}"
    assert audit.acao == "prazo_cumprido"


def test_alertas_derivados_dos_prazos(client, db_session, seeded):
    from datetime import date, timedelta

    today = date.today()
    proc = seeded
    db_session.add_all(
        [
            models.Prazo(
                processo_id=proc.id, escritorio_id=proc.escritorio_id, descricao="Vencido", data_inicio=today - timedelta(days=20),
                dias=15, dias_uteis=True, data_fatal=today - timedelta(days=2), cumprido=False,
            ),
            models.Prazo(
                processo_id=proc.id, escritorio_id=proc.escritorio_id, descricao="Hoje", data_inicio=today - timedelta(days=15),
                dias=15, dias_uteis=True, data_fatal=today, cumprido=False,
            ),
            models.Prazo(
                processo_id=proc.id, escritorio_id=proc.escritorio_id, descricao="Amanha", data_inicio=today - timedelta(days=14),
                dias=15, dias_uteis=True, data_fatal=today + timedelta(days=1), cumprido=False,
            ),
            models.Prazo(
                processo_id=proc.id, escritorio_id=proc.escritorio_id, descricao="D3", data_inicio=today - timedelta(days=12),
                dias=15, dias_uteis=True, data_fatal=today + timedelta(days=3), cumprido=False,
            ),
            models.Prazo(
                processo_id=proc.id, escritorio_id=proc.escritorio_id, descricao="Longe", data_inicio=today,
                dias=15, dias_uteis=True, data_fatal=today + timedelta(days=10), cumprido=False,
            ),
            models.Prazo(
                processo_id=proc.id, escritorio_id=proc.escritorio_id, descricao="CumpridoHoje", data_inicio=today - timedelta(days=15),
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
        escritorio_id=seeded.escritorio_id,
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
        processo_id=seeded.id,
        escritorio_id=seeded.escritorio_id, tipo="Contestacao", conteudo="m", status="rascunho"
    )
    db_session.add(peticao)
    db_session.flush()

    resp = client.post(f"/peticoes/{peticao.id}/approve")

    assert resp.status_code == 200
    seed_user = db_session.query(models.Usuario).first()
    audit = db_session.query(models.AuditLog).filter_by(acao="peticao_aprovada").one()
    assert audit.ator == f"usuario:{seed_user.id}"
    assert audit.entidade_id == peticao.id


def test_editar_peticao_atualiza_conteudo_e_audita(client, db_session, seeded):
    peticao = models.Peticao(
        processo_id=seeded.id,
        escritorio_id=seeded.escritorio_id, tipo="Contestacao", conteudo="rascunho inicial", status="rascunho"
    )
    db_session.add(peticao)
    db_session.flush()

    resp = client.patch(
        f"/peticoes/{peticao.id}",
        json={"conteudo": "texto revisado"},
    )

    assert resp.status_code == 200
    assert resp.json()["conteudo"] == "texto revisado"
    seed_user = db_session.query(models.Usuario).first()
    audit = db_session.query(models.AuditLog).filter_by(acao="peticao_editada").one()
    assert audit.ator == f"usuario:{seed_user.id}"
    assert audit.entidade_id == peticao.id


def test_editar_peticao_permite_transicao_para_revisao(client, db_session, seeded):
    peticao = models.Peticao(
        processo_id=seeded.id,
        escritorio_id=seeded.escritorio_id, tipo="Contestacao", conteudo="m", status="rascunho"
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
        processo_id=seeded.id,
        escritorio_id=seeded.escritorio_id, tipo="Contestacao", conteudo="m", status="rascunho"
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
        escritorio_id=seeded.escritorio_id,
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
            models.AuditLog(
                escritorio_id=seeded.escritorio_id, ator="usuario:1",
                acao="prazo_revisado", entidade="prazo", entidade_id=1,
            ),
            models.AuditLog(
                escritorio_id=seeded.escritorio_id, ator="system",
                acao="captura_oab_executada", entidade="escritorio", entidade_id=1,
            ),
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
        escritorio_id=seeded.escritorio_id,
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
        escritorio_id=seeded.escritorio_id,
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
    # "Adv Seed" vem do fixture seeded; depois os dois criados aqui.
    assert [u["nome"] for u in body] == ["Adv Seed", "Dra. Helena", "Rafael"]
    assert all(u["escritorio_id"] == seeded.escritorio_id for u in body)


def test_listar_jobs_mais_recentes_primeiro_com_filtros(client, db_session, seeded):
    peticao = models.Peticao(
        processo_id=seeded.id,
        escritorio_id=seeded.escritorio_id,
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
        escritorio_id=seeded.escritorio_id,
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
        escritorio_id=seeded.escritorio_id,
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
        escritorio_id=seeded.escritorio_id,
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


def test_protocolar_async_pje_prepara_sem_marcar_protocolada(client, db_session, seeded):
    seeded.sistema = "PJe"
    peticao = models.Peticao(
        processo_id=seeded.id,
        escritorio_id=seeded.escritorio_id,
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
    assert body["status"] == "completed"
    assert body["payload"]["sistema"] == "PJe"
    assert body["payload"]["modo"] == "pje_assistido_playwright"
    assert body["resultado"]["checkpoint"] == "ready_to_sign"
    assert body["resultado"]["irreversible"] is False
    assert "protocolo" not in body["resultado"]

    db_session.refresh(peticao)
    assert peticao.status == "aprovada"
    assert peticao.protocolada_em is None

    audit = db_session.query(models.AuditLog).filter_by(
        acao="peticao_protocolo_preparado"
    ).one()
    assert audit.detalhe["checkpoint"] == "ready_to_sign"


def test_confirmar_protocolo_pje_marca_protocolada_e_audita(client, db_session, seeded):
    seeded.sistema = "PJe"
    peticao = models.Peticao(
        processo_id=seeded.id,
        escritorio_id=seeded.escritorio_id,
        tipo="Contestacao",
        conteudo="minuta",
        status="aprovada",
        aprovada_por=7,
    )
    db_session.add(peticao)
    db_session.flush()

    resp = client.post(
        f"/peticoes/{peticao.id}/protocolar/confirmar",
        json={"protocolo": "PJE-2026-0001", "comprovante_uri": "s3://comprovante.pdf"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "protocolada"
    assert body["protocolada_em"] is not None

    audit = db_session.query(models.AuditLog).filter_by(acao="peticao_protocolada").one()
    assert audit.detalhe["protocolo"] == "PJE-2026-0001"
    assert audit.detalhe["origem"] == "pje_assistido"


def test_confirmar_protocolo_com_credencial_audita_provedor_modo(client, db_session, seeded):
    seeded.sistema = "PJe"
    usuario = models.Usuario(
        escritorio_id=seeded.escritorio_id, nome="Adv", email="conf@example.com"
    )
    db_session.add(usuario)
    db_session.flush()
    peticao = models.Peticao(
        processo_id=seeded.id,
        escritorio_id=seeded.escritorio_id,
        tipo="Manifestacao",
        conteudo="minuta",
        status="aprovada",
        aprovada_por=usuario.id,
    )
    db_session.add(peticao)
    db_session.flush()
    cred = client.post(
        f"/usuarios/{usuario.id}/credenciais-assinatura",
        json={"provedor": "birdid", "referencia_externa": "adv@birdid.example"},
    ).json()

    resp = client.post(
        f"/peticoes/{peticao.id}/protocolar/confirmar",
        json={"protocolo": "PJE-2026-0009", "credencial_id": cred["id"]},
    )

    assert resp.status_code == 200
    audit = db_session.query(models.AuditLog).filter_by(acao="peticao_protocolada").one()
    assert audit.detalhe["provedor"] == "birdid"
    assert audit.detalhe["modo"] == "manual_handoff"


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
    assert body["modo"] == "manual_handoff"
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


def test_cadastrar_sessao_pje_guarda_referencia_sem_vazar_storage_state(client, db_session, seeded):
    usuario = db_session.query(models.Usuario).first()
    storage_state = {
        "cookies": [{"name": "JSESSIONID", "value": "cookie-super-sensivel"}],
        "origins": [],
    }

    resp = client.post(
        f"/usuarios/{usuario.id}/pje-sessoes",
        json={
            "tribunal": "TRF3",
            "url_base": "https://pje1g.trf3.jus.br/pje",
            "storage_state": storage_state,
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["provedor"] == "PJeSession"
    assert body["referencia_vault"].startswith("localdev://assinatura/")
    assert "cookie-super-sensivel" not in str(body)

    audit = db_session.query(models.AuditLog).filter_by(acao="sessao_pje_cadastrada").one()
    assert audit.detalhe == {"tribunal": "TRF3"}
    assert "cookie-super-sensivel" not in str(audit.detalhe)


def test_cadastrar_sessao_pje_rejeita_senha_ou_certificado(client, db_session, seeded):
    usuario = db_session.query(models.Usuario).first()

    resp = client.post(
        f"/usuarios/{usuario.id}/pje-sessoes",
        json={
            "tribunal": "TRF3",
            "url_base": "https://pje1g.trf3.jus.br/pje",
            "storage_state": {"cookies": [], "senha_pje": "nao"},
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
        json={"oab": "12345", "uf": "SP", "intervalo_horas": 6},
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


def test_remover_oab_monitorada_apaga_dados_capturados(client, db_session, seeded):
    oab = models.OabMonitorada(
        escritorio_id=seeded.escritorio_id,
        oab="206575",
        uf="SP",
        ativo=True,
    )
    db_session.add(oab)
    db_session.flush()
    processo = models.Processo(escritorio_id=seeded.escritorio_id, numero="123")
    db_session.add(processo)
    db_session.flush()
    intimacao = models.Intimacao(
        processo_id=processo.id,
        escritorio_id=seeded.escritorio_id,
        fonte="DJEN",
        fonte_id="target-oab",
        numero_processo=processo.numero,
        tipo_comunicacao="Intimacao",
        data_disponibilizacao=date(2026, 6, 22),
        payload={
            "destinatarioadvogados": [
                {"advogado": {"numero_oab": "206575", "uf_oab": "SP"}}
            ]
        },
    )
    outra_intimacao = models.Intimacao(
        escritorio_id=seeded.escritorio_id,
        fonte="DJEN",
        fonte_id="other-oab",
        numero_processo="456",
        tipo_comunicacao="Intimacao",
        data_disponibilizacao=date(2026, 6, 22),
        payload={
            "destinatarioadvogados": [
                {"advogado": {"numero_oab": "999999", "uf_oab": "SP"}}
            ]
        },
    )
    db_session.add_all([intimacao, outra_intimacao])
    db_session.flush()
    prazo = models.Prazo(
        processo_id=processo.id,
        intimacao_id=intimacao.id,
        escritorio_id=seeded.escritorio_id,
        descricao="Prazo alvo",
        data_inicio=date(2026, 6, 23),
        dias=15,
        dias_uteis=True,
        data_fatal=date(2026, 7, 14),
    )
    db_session.add(prazo)
    db_session.flush()
    peticao = models.Peticao(
        escritorio_id=seeded.escritorio_id,
        processo_id=processo.id,
        prazo_id=prazo.id,
        tipo="Manifestacao",
    )
    db_session.add(peticao)
    db_session.flush()
    db_session.add_all(
        [
            models.Documento(processo_id=processo.id, nome="doc processo"),
            models.Documento(peticao_id=peticao.id, nome="doc peticao"),
            models.Andamento(processo_id=processo.id, codigo=1),
            models.AuditLog(
                escritorio_id=seeded.escritorio_id,
                ator="agent:capture",
                acao="captura_oab_executada",
                entidade="escritorio",
                entidade_id=seeded.escritorio_id,
                detalhe={"oab": "206575", "uf": "SP"},
            ),
        ]
    )
    db_session.commit()

    resp = client.delete(f"/capturas/oab/{oab.id}?purge=true")

    assert resp.status_code == 200
    body = resp.json()
    assert body["removidos"]["intimacoes"] == 1
    assert body["removidos"]["prazos"] == 1
    assert body["removidos"]["peticoes"] == 1
    assert body["removidos"]["processos"] == 1
    assert db_session.get(models.OabMonitorada, oab.id) is None
    assert db_session.get(models.Intimacao, intimacao.id) is None
    assert db_session.get(models.Prazo, prazo.id) is None
    assert db_session.get(models.Peticao, peticao.id) is None
    assert db_session.get(models.Processo, processo.id) is None
    assert db_session.get(models.Intimacao, outra_intimacao.id) is not None
