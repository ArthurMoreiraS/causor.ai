"""TestClient TDD for the read-only API."""

import base64
import io
from datetime import date, timedelta
from unittest.mock import patch

import pytest
from PIL import Image
from pypdf import PdfReader

from app.agent.classifier import ClassificacaoIntimacao
from app.agent.drafter import MinutaGerada
from app.settings import settings
from app.sor import models
from sqlalchemy import select
from tests.conftest import seed_filing_ready, seed_ready_context


@pytest.fixture(autouse=True)
def _no_background_enrichment(monkeypatch):
    # /capture/oab agenda o backfill de enriquecimento como background task. A
    # .env de dev traz datajud_api_key, então o gate ligaria em todo teste e o
    # background task abriria um SessionLocal real (fora do db_session de teste),
    # travando. Neutraliza por padrão; o teste que exercita o agendamento
    # re-patcha este alvo com um spy.
    monkeypatch.setattr("app.api.main.run_enrichment_backfill", lambda *a, **k: None)


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_capture_oab_defaults_to_bounded_lookback(client, seeded):
    class FakeDjen:
        def __init__(self):
            self.calls = []

        def consultar(self, oab, uf, **kw):
            self.calls.append((oab, uf, kw))
            return []

    fake_djen = FakeDjen()
    today_before = date.today()

    with patch("app.api.main.DjenClient", return_value=fake_djen):
        resp = client.post("/capture/oab", json={"oab": "12345", "uf": "SP"})

    today_after = date.today()

    assert resp.status_code == 200
    assert resp.json() == {
        "intimacoes_novas": 0,
        "processos_enriquecidos": 0,
        "prazos_registrados": 0,
        "prazos_historicos": 0,
        "djen_indisponivel": False,
        "djen_erro": None,
    }
    assert fake_djen.calls[0][0:2] == ("12345", "SP")
    params = fake_djen.calls[0][2]
    assert today_before <= params["data_fim"] <= today_after
    # O que importa é a janela existir e vir do setting (ajustável sem quebrar o
    # teste); um limite ausente faria a captura varrer o histórico inteiro da OAB.
    assert 0 < settings.capture_manual_lookback_days <= 365
    assert params["data_inicio"] == params["data_fim"] - timedelta(
        days=settings.capture_manual_lookback_days
    )


def test_capture_oab_defers_datajud_enrichment(client, seeded, monkeypatch):
    """Captura manual roda em modo rápido: NÃO chama DataJud no request.

    O enriquecimento passa a ser on-demand (na geração da minuta). A captura só
    grava intimações + prazos e deixa o processo como "shell"; isso evita o loop
    sequencial de DataJud que trava a UI e é rate-limitado pelo CNJ em volume.
    """
    from app.capture.djen import ComunicacaoDTO

    # Disponibilização recente: a captura não registra prazo cujo vencimento
    # provisório já passou, então uma data fixa de 2024 faria o assert de
    # `prazos_registrados` depender do relógio da máquina.
    disponibilizacao = (date.today() - timedelta(days=2)).isoformat()

    class FakeDjen:
        def consultar(self, oab, uf, **kw):
            return [
                ComunicacaoDTO.from_item(
                    {
                        "id": "555",
                        "numero_processo": "0000001-00.2024.8.26.0100",
                        "siglaTribunal": "TJSP",
                        "tipoComunicacao": "Intimação",
                        "texto": "Intimada para manifestar em 15 dias.",
                        "data_disponibilizacao": disponibilizacao,
                    }
                )
            ]

    class SpyDatajud:
        def __init__(self):
            self.calls = []

        def consultar_processo(self, numero_processo, *, tribunal):
            self.calls.append((numero_processo, tribunal))
            return None

    spy = SpyDatajud()
    # Força o caminho DataJud-ativo: sem key o endpoint usaria _NoopDatajudClient
    # e o teste passaria trivialmente (não provaria o desacoplamento).
    monkeypatch.setattr("app.api.main.settings.datajud_api_key", "test-key")

    with patch("app.api.main.DjenClient", return_value=FakeDjen()), patch(
        "app.api.main.DatajudClient", return_value=spy
    ):
        resp = client.post("/capture/oab", json={"oab": "12345", "uf": "SP"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["intimacoes_novas"] == 1
    assert body["prazos_registrados"] == 0
    assert body["processos_enriquecidos"] == 0
    assert spy.calls == []  # DataJud não foi chamado durante a captura


def test_capture_oab_schedules_enrichment_backfill(client, seeded, monkeypatch):
    """Após a captura rápida, o endpoint agenda o backfill de enriquecimento do
    tenant como background task (fora do request). É assim que os processos shell
    ganham sistema/classe/órgão sem travar a captura nem exigir worker separado.
    """
    scheduled: list[int] = []

    class FakeDjen:
        def consultar(self, oab, uf, **kw):
            return []

    monkeypatch.setattr("app.api.main.settings.datajud_api_key", "test-key")
    monkeypatch.setattr(
        "app.api.main.run_enrichment_backfill",
        lambda escritorio_id, **kw: scheduled.append(escritorio_id),
    )

    with patch("app.api.main.DjenClient", return_value=FakeDjen()):
        resp = client.post("/capture/oab", json={"oab": "12345", "uf": "SP"})

    assert resp.status_code == 200
    assert scheduled == [seeded.escritorio_id]


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


def test_dashboard_operacional_expoe_vencidos_e_aprovadas(client, db_session, seeded):
    # Fixture já traz o prazo "A" pendente com data_fatal em 2024 (vencido hoje).
    db_session.add_all(
        [
            models.Peticao(processo_id=seeded.id, escritorio_id=seeded.escritorio_id, status="aprovada"),
            models.Peticao(processo_id=seeded.id, escritorio_id=seeded.escritorio_id, status="rascunho"),
        ]
    )
    db_session.flush()

    body = client.get("/dashboard/operational").json()
    metric_by_key = {item["key"]: item["value"] for item in body["metrics"]}

    assert metric_by_key["vencidos"] == 1  # prazo "A" está pendente e com data_fatal no passado
    assert metric_by_key["aprovadas"] == 1
    assert metric_by_key["minutas"] == 1  # rascunho


def test_processos_resumo_conta_e_enriquece(client, db_session, seeded):
    # seeded: 1 processo, 1 intimação (tipo "Intimação"), prazo "A" pendente
    # (data_fatal 2024-09-30) e prazo "B" cumprido (2024-09-16).
    db_session.add_all(
        [
            models.Peticao(
                processo_id=seeded.id, escritorio_id=seeded.escritorio_id,
                tipo="Contestacao", status="rascunho",
            ),
            models.Peticao(
                processo_id=seeded.id, escritorio_id=seeded.escritorio_id,
                tipo="Embargos", status="aprovada",
            ),
        ]
    )
    db_session.flush()

    resp = client.get("/processos/resumo")
    assert resp.status_code == 200
    body = resp.json()

    assert body["total"] == 1
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["id"] == seeded.id
    assert item["numero"] == "00000010020248260100"
    assert item["intimacoes_count"] == 1
    assert item["peticoes_count"] == 2
    # próximo prazo = menor data_fatal pendente; o cumprido "B" é ignorado.
    assert item["proximo_prazo"]["data_fatal"] == "2024-09-30"
    assert item["proximo_prazo"]["cumprido"] is False
    assert item["intimacao_tipo"] == "Intimação"
    # peticao_tipo = a de maior id (Embargos, adicionada por último).
    assert item["peticao_tipo"] == "Embargos"


def test_processos_resumo_sem_prazo_pendente_retorna_none(client, db_session, seeded):
    proc = models.Processo(escritorio_id=seeded.escritorio_id, numero="00000020020248260100")
    db_session.add(proc)
    db_session.flush()
    db_session.add(
        models.Prazo(
            processo_id=proc.id, escritorio_id=seeded.escritorio_id, descricao="C",
            data_inicio=date(2024, 9, 9), dias=5, dias_uteis=True,
            data_fatal=date(2024, 9, 20), cumprido=True,
        )
    )
    db_session.flush()

    body = client.get("/processos/resumo").json()
    item = next(i for i in body["items"] if i["id"] == proc.id)
    assert item["proximo_prazo"] is None
    assert item["intimacoes_count"] == 0
    assert item["peticoes_count"] == 0
    assert item["intimacao_tipo"] is None
    assert item["peticao_tipo"] is None


def test_processos_resumo_respeita_tenant(client, db_session, seeded):
    other = models.Escritorio(nome="Outro Escritório")
    db_session.add(other)
    db_session.flush()
    outro_proc = models.Processo(escritorio_id=other.id, numero="00000099020248260100")
    db_session.add(outro_proc)
    db_session.flush()

    body = client.get("/processos/resumo").json()
    assert body["total"] == 1
    assert [i["id"] for i in body["items"]] == [seeded.id]


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
    seed_ready_context(db_session, seeded)
    intimacao = db_session.query(models.Intimacao).one()
    classificacao = ClassificacaoIntimacao(
        tipo="Intimacao para contestar",
        peticao_sugerida="Contestacao",
        prazo_dias=15,
        dias_uteis=True,
        confianca=0.91,
        resumo="Reu intimado para contestar.",
    )

    minuta = MinutaGerada(
        contexto_consolidado="ctx",
        analise_providencia="analise",
        minuta="MINUTA",
        alertas=["revisar"],
        confianca=0.8,
    )
    with (
        patch("app.agent.service.classify_intimacao", return_value=classificacao),
        patch("app.agent.service.draft_peticao", return_value=minuta),
    ):
        resp = client.post(
            f"/intimacoes/{intimacao.id}/draft",
            json={"calendar_years": [2024, 2025]},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["peticao"]["status"] == "rascunho"
    assert body["peticao"]["conteudo"] == "MINUTA"
    assert body["peticao"]["dossie"]["analise_providencia"] == "analise"
    assert "revisar" in body["peticao"]["dossie"]["alertas"]
    assert body["prazo"]["dias"] == 15  # reutiliza o prazo em aberto
    assert body["classificacao"]["peticao_sugerida"] == "Contestacao"


def test_gerar_minuta_audita(client, db_session, seeded):
    seed_ready_context(db_session, seeded)
    intimacao = db_session.query(models.Intimacao).one()
    classificacao = ClassificacaoIntimacao(
        tipo="Intimacao para contestar",
        peticao_sugerida="Contestacao",
        prazo_dias=15,
        dias_uteis=True,
        confianca=0.9,
        resumo="Reu intimado.",
    )
    minuta = MinutaGerada(
        contexto_consolidado="ctx",
        analise_providencia="analise",
        minuta="MINUTA",
        alertas=[],
        confianca=0.8,
    )
    with (
        patch("app.agent.service.classify_intimacao", return_value=classificacao),
        patch("app.agent.service.draft_peticao", return_value=minuta),
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
    assert audit.escritorio_id == seeded.escritorio_id

    visible_audit = client.get("/audit", params={"entidade": "job_execucao"}).json()
    assert [row["id"] for row in visible_audit] == [audit.id]


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


def test_protocolar_async_sem_sessao_conectada_job_falha_pedindo_conexao(client, db_session, seeded):
    """Qualquer sistema roteia pelo driver; sem sessao no cofre o job falha
    pedindo pra conectar o tribunal (nao mais 409 de 'sistema sem conector')."""
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
    seed_filing_ready(db_session, peticao)

    resp = client.post(f"/peticoes/{peticao.id}/protocolar/async")

    assert resp.status_code == 200
    job = resp.json()
    assert job["status"] == "failed"
    assert "conecte" in (job["erro"] or "").lower()
    db_session.refresh(peticao)
    assert peticao.status == "aprovada"  # nao protocolada


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
    """Listagem de jobs retorna mais recentes primeiro e filtra por tipo/status."""
    capture = client.post(
        "/jobs/capture/oab",
        json={"oab": "123456", "uf": "SP", "escritorio_id": seeded.escritorio_id},
    ).json()

    todos = client.get("/jobs").json()
    assert [job["id"] for job in todos] == [capture["id"]]

    so_cap = client.get("/jobs", params={"tipo": "captura_oab"}).json()
    assert [job["id"] for job in so_cap] == [capture["id"]]
    assert so_cap[0]["status"] == "queued"

    so_queued = client.get("/jobs", params={"status": "queued"}).json()
    assert [job["id"] for job in so_queued] == [capture["id"]]

    none_completed = client.get("/jobs", params={"status": "completed"}).json()
    assert none_completed == []


def test_job_agendado_por_oab_respeita_tenant(client, db_session, seeded):
    own_oab = models.OabMonitorada(
        escritorio_id=seeded.escritorio_id,
        oab="123456",
        uf="SP",
    )
    other_office = models.Escritorio(nome="Outro Escritório")
    db_session.add_all([own_oab, other_office])
    db_session.flush()
    other_oab = models.OabMonitorada(
        escritorio_id=other_office.id,
        oab="999999",
        uf="RJ",
    )
    db_session.add(other_oab)
    db_session.flush()
    own_job = models.JobExecucao(
        tipo="captura_oab",
        status="completed",
        entidade="oab_monitorada",
        entidade_id=own_oab.id,
    )
    other_job = models.JobExecucao(
        tipo="captura_oab",
        status="completed",
        entidade="oab_monitorada",
        entidade_id=other_oab.id,
    )
    db_session.add_all([own_job, other_job])
    db_session.flush()

    jobs = client.get("/jobs").json()

    assert [job["id"] for job in jobs] == [own_job.id]
    assert client.get(f"/jobs/{own_job.id}").status_code == 200
    assert client.get(f"/jobs/{other_job.id}").status_code == 404


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
    """Submit real exige sessao PJe no vault; sem sessao o job falha, mas o
    credencial_id e registrado no payload do job e a referencia externa (segredo)
    nunca vaza no job nem na auditoria."""
    seeded.sistema = "PJe"
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
    seed_filing_ready(db_session, peticao)

    resp = client.post(
        f"/peticoes/{peticao.id}/protocolar/async",
        json={"credencial_id": credencial["id"]},
    )

    assert resp.status_code == 200
    body = resp.json()
    # Sem sessao PJe no vault -> job failed (reverte p/ aprovada), nao protocolada.
    assert body["status"] == "failed"
    assert body["payload"]["credencial_id"] == credencial["id"]
    # segredo/referência externa nunca aparece no job nem na auditoria
    assert "birdid-account-123" not in str(body)

    db_session.refresh(peticao)
    assert peticao.status == "aprovada"
    assert peticao.protocolada_em is None
    # Nenhum registro de peticao_protocolada (o ato irreversivel nao aconteceu).
    assert (
        db_session.query(models.AuditLog).filter_by(acao="peticao_protocolada").count() == 0
    )


def test_protocolar_async_com_credencial_inexistente_retorna_404(client, db_session, seeded):
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
    seed_filing_ready(db_session, peticao)

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
    seed_filing_ready(db_session, peticao)

    resp = client.post(
        f"/peticoes/{peticao.id}/protocolar/async",
        json={"credencial_id": credencial["id"]},
    )

    assert resp.status_code == 409
    db_session.refresh(peticao)
    assert peticao.status == "aprovada"


def test_protocolar_async_pje_sem_sessao_falha_e_nao_protocola(client, db_session, seeded):
    """Sem sessao conectada no agente local, o submit real nao pode prosseguir:
    job failed, peticao continua 'aprovada' (reverte de 'protocolando') e nada e
    marcado como protocolada — o ato irreversivel nunca e simulado."""
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
    seed_filing_ready(db_session, peticao)

    resp = client.post(f"/peticoes/{peticao.id}/protocolar/async")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "failed"
    assert "conecte" in (body["erro"] or "").lower()
    db_session.refresh(peticao)
    assert peticao.status == "aprovada"  # revertido, NAO protocolada
    assert peticao.protocolada_em is None


def test_protocolar_async_pje_sem_orgao_enriquece_on_demand(
    client, db_session, seeded, monkeypatch
):
    """Processo sem orgao_julgador: o job enriquece on-demand via DataJud
    antes de acionar o conector. Garante que o Playwright recebe o orgao."""
    from app.capture.datajud import ProcessoDTO
    from unittest.mock import patch

    # Força o caminho DataJud-ativo: sem key o endpoint usaria _NoopDatajudClient
    # e o mock de DatajudClient abaixo seria ignorado (teste passaria so por
    # acidente, dependendo de haver ou nao datajud_api_key no ambiente).
    monkeypatch.setattr("app.api.main.settings.datajud_api_key", "test-key")

    seeded.sistema = "PJe"
    seeded.orgao_julgador = None  # shell, precisa enriquecer
    seeded.classe = None
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
    seed_filing_ready(db_session, peticao)

    processo_dto = ProcessoDTO.from_source(
        {
            "numeroProcesso": "00000010020248260100",
            "classe": {"nome": "Procedimento Comum Civel"},
            "tribunal": "TJSP",
            "orgaoJulgador": "1a Vara Civel",
            "sistema": {"nome": "PJe"},
        }
    )

    fake = type("FakeD", (), {
        "consultar_processo": lambda self, n, *, tribunal: processo_dto
    })()
    with patch("app.api.main.DatajudClient", return_value=fake):
        resp = client.post(f"/peticoes/{peticao.id}/protocolar/async")

    assert resp.status_code == 200
    body = resp.json()
    # enriqueceu on-demand (goal do teste) — orgao agora preenchido
    db_session.refresh(seeded)
    assert seeded.orgao_julgador == "1a Vara Civel"
    # submit sem sessao no vault -> job failed, peticao voltou a aprovada
    assert body["status"] == "failed"
    db_session.refresh(peticao)
    assert peticao.status == "aprovada"
    assert peticao.protocolada_em is None


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
    assert audit.detalhe["origem"] == "declaracao_manual"
    assert audit.detalhe["comprovante_status"] == "referencia_nao_verificada"


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


def _png_para_upload(largura: int = 10, altura: int = 10) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (largura, altura), "red").save(buf, format="PNG")
    return buf.getvalue()


def test_settings_profile_atualiza_timbrado(client, db_session, seeded):
    resp = client.patch(
        "/settings/profile",
        json={
            "timbrado_cabecalho": "Rua X, 100 - São Paulo/SP",
            "timbrado_rodape": "OAB/SP 123.456 · causor.com",
            "timbrado_logo": base64.b64encode(_png_para_upload()).decode("ascii"),
        },
    )

    assert resp.status_code == 200
    esc = resp.json()["escritorio"]
    assert esc["timbrado_cabecalho"] == "Rua X, 100 - São Paulo/SP"
    assert esc["timbrado_rodape"] == "OAB/SP 123.456 · causor.com"
    armazenado = base64.b64decode(esc["timbrado_logo"])
    assert armazenado.startswith(b"\x89PNG")

    lido = client.get("/settings/profile").json()["escritorio"]
    assert lido["timbrado_cabecalho"] == "Rua X, 100 - São Paulo/SP"
    assert lido["timbrado_logo"] == esc["timbrado_logo"]


def test_settings_profile_remove_logo_com_string_vazia(client, db_session, seeded):
    client.patch(
        "/settings/profile",
        json={"timbrado_logo": base64.b64encode(_png_para_upload()).decode("ascii")},
    )

    resp = client.patch("/settings/profile", json={"timbrado_logo": ""})

    assert resp.status_code == 200
    assert resp.json()["escritorio"]["timbrado_logo"] is None


def test_settings_profile_rejeita_logo_invalido(client, db_session, seeded):
    nao_imagem = client.patch(
        "/settings/profile",
        json={"timbrado_logo": base64.b64encode(b"nao-e-imagem").decode("ascii")},
    )
    assert nao_imagem.status_code == 422

    base64_quebrado = client.patch("/settings/profile", json={"timbrado_logo": "###"})
    assert base64_quebrado.status_code == 422


def test_settings_profile_rejeita_timbrado_cabecalho_com_muitas_linhas(client, db_session, seeded):
    nove_linhas = "\n".join(f"linha {i}" for i in range(9))

    resp = client.patch("/settings/profile", json={"timbrado_cabecalho": nove_linhas})

    assert resp.status_code == 422


def test_settings_profile_rejeita_timbrado_rodape_com_muitas_linhas(client, db_session, seeded):
    cinco_linhas = "\n".join(f"linha {i}" for i in range(5))

    resp = client.patch("/settings/profile", json={"timbrado_rodape": cinco_linhas})

    assert resp.status_code == 422


def test_settings_profile_aceita_timbrado_no_limite_de_linhas(client, db_session, seeded):
    oito_linhas = "\n".join(f"linha {i}" for i in range(8))
    quatro_linhas = "\n".join(f"linha {i}" for i in range(4))

    resp = client.patch(
        "/settings/profile",
        json={"timbrado_cabecalho": oito_linhas, "timbrado_rodape": quatro_linhas},
    )

    assert resp.status_code == 200


def _cria_peticao(db_session, seeded, escritorio_id=None, processo_id=None):
    pet = models.Peticao(
        escritorio_id=escritorio_id if escritorio_id is not None else seeded.escritorio_id,
        processo_id=processo_id if processo_id is not None else seeded.id,
        tipo="Manifestacao",
        conteudo="Excelentíssimo Juízo, requer a juntada.",
        status="rascunho",
    )
    db_session.add(pet)
    db_session.flush()
    return pet


def test_peticao_pdf_download(client, db_session, seeded):
    pet = _cria_peticao(db_session, seeded)

    resp = client.get(f"/peticoes/{pet.id}/pdf")

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/pdf")
    assert resp.content.startswith(b"%PDF")
    assert "minuta-" in resp.headers["content-disposition"]


def test_peticao_pdf_usa_timbrado_do_escritorio(client, db_session, seeded):
    esc = db_session.get(models.Escritorio, seeded.escritorio_id)
    esc.timbrado_rodape = "OAB/SP 123.456"
    db_session.flush()
    pet = _cria_peticao(db_session, seeded)

    resp = client.get(f"/peticoes/{pet.id}/pdf")

    paginas = PdfReader(io.BytesIO(resp.content)).pages
    texto = "\n".join(p.extract_text() or "" for p in paginas)
    assert "Escritório Teste" in texto
    assert "OAB/SP 123.456" in texto


def test_peticao_pdf_de_outro_tenant_retorna_404(client, db_session, seeded):
    outro = models.Escritorio(nome="Outro Escritório")
    db_session.add(outro)
    db_session.flush()
    proc2 = models.Processo(
        escritorio_id=outro.id, numero="0000002-00.2024.8.26.0100", tribunal="TJSP"
    )
    db_session.add(proc2)
    db_session.flush()
    pet2 = _cria_peticao(db_session, seeded, escritorio_id=outro.id, processo_id=proc2.id)

    resp = client.get(f"/peticoes/{pet2.id}/pdf")

    assert resp.status_code == 404
