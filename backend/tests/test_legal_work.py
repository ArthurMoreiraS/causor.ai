import pytest

from app.sor import models
from app.agent.drafter import MinutaGerada
from tests.conftest import seed_ready_context


def test_manual_process_is_canonical_and_deduplicated(client, db_session, seeded):
    before = db_session.query(models.Intimacao).count(), db_session.query(models.Prazo).count()
    payload = {"numero": "0000123-45.2026.8.26.0100", "tribunal": "TJSP"}
    first = client.post("/processos", json=payload)
    assert first.status_code == 201, first.text
    second = client.post("/processos", json={**payload, "numero": "00001234520268260100"})
    assert second.status_code == 200, second.text
    assert second.json()["id"] == first.json()["id"]
    assert first.json()["numero"] == "00001234520268260100"
    assert before == (db_session.query(models.Intimacao).count(), db_session.query(models.Prazo).count())
    assert client.post("/processos", json={"numero": "ABC123"}).status_code == 422


def test_manual_work_persists_without_notice_or_deadline(client, db_session, seeded):
    before = db_session.query(models.Intimacao).count(), db_session.query(models.Prazo).count()
    result = client.post("/trabalhos", json={"processo_id": seeded.id, "providencia": "Manifestação", "instrucoes": "Conferir os documentos recebidos", "grau": "1"})
    assert result.status_code == 201, result.text
    work = result.json()
    assert work["intimacao_id"] is None and work["prazo_id"] is None
    assert client.get(f"/trabalhos/{work['id']}").json()["instrucoes"] == "Conferir os documentos recebidos"
    assert client.get("/trabalhos", params={"processo_id": seeded.id}).json()["total"] == 1
    patch = {"versao": work["versao"], "instrucoes": "Conferir também o laudo"}
    assert client.patch(f"/trabalhos/{work['id']}", json=patch).status_code == 200
    assert client.patch(f"/trabalhos/{work['id']}", json=patch).status_code == 409
    assert before == (db_session.query(models.Intimacao).count(), db_session.query(models.Prazo).count())


def test_work_rejects_cross_tenant_and_mismatched_sources(client, db_session, seeded):
    office = models.Escritorio(nome="Outro")
    db_session.add(office)
    db_session.flush()
    process = models.Processo(escritorio_id=office.id, numero="outro")
    customer = models.Cliente(escritorio_id=office.id, nome="Privado")
    db_session.add_all([process, customer])
    db_session.commit()
    assert client.post("/trabalhos", json={"processo_id": process.id, "providencia": "Revisar"}).status_code == 404
    assert client.post("/processos", json={"numero": "00001234520268260100", "cliente_id": customer.id}).status_code == 404
    another = models.Processo(escritorio_id=seeded.escritorio_id, numero="outro-local")
    db_session.add(another)
    db_session.flush()
    notice = db_session.query(models.Intimacao).first()
    assert client.post("/trabalhos", json={"processo_id": another.id, "providencia": "Revisar", "intimacao_id": notice.id}).status_code == 422


def test_existing_process_is_never_silently_reassigned(client, db_session, seeded):
    payload = {"numero": "00001234520268260100", "tribunal": "TJSP"}
    first = client.post("/processos", json=payload)
    assert first.status_code == 201
    customer = models.Cliente(escritorio_id=seeded.escritorio_id, nome="Outro cliente")
    db_session.add(customer)
    db_session.commit()
    response = client.post("/processos", json={**payload, "cliente_id": customer.id})
    assert response.status_code == 409


def prepared_work(client, db_session, seeded, monkeypatch, *, linked=False):
    from app.agent import work_service
    customer = models.Cliente(escritorio_id=seeded.escritorio_id, nome="Parte representada")
    db_session.add(customer)
    db_session.flush()
    seeded.cliente_id = customer.id
    seed_ready_context(db_session, seeded)
    db_session.commit()
    monkeypatch.setattr(work_service, "analyze_sources", lambda **kwargs: {"fatos": [], "cronologia": [], "contradicoes": [], "lacunas": ["Conferir contrato"]})
    payload = {"processo_id": seeded.id, "providencia": "Manifestação", "polo": "Autor"}
    if linked:
        payload["intimacao_id"] = db_session.query(models.Intimacao).filter_by(processo_id=seeded.id).first().id
        payload["prazo_id"] = db_session.query(models.Prazo).filter_by(processo_id=seeded.id).first().id
    work = client.post("/trabalhos", json=payload).json()
    work = client.put(f"/trabalhos/{work['id']}/escopo", json={"versao": work["versao"],
        "data_referencia": "2026-09-01", "declaracao": "Documentos sintéticos para teste; instâncias não verificadas."}).json()
    response = client.post(f"/trabalhos/{work['id']}/evidencias", json={"versao": work["versao"]})
    assert response.status_code == 200, response.text
    return response.json()


def test_work_drafts_without_fabricating_notice_and_requires_evidence_review(client, db_session, seeded, monkeypatch):
    from app.agent import work_service
    work = prepared_work(client, db_session, seeded, monkeypatch)
    counts = db_session.query(models.Intimacao).count(), db_session.query(models.Prazo).count()
    url = f"/trabalhos/{work['id']}"
    assert client.post(url + "/minuta", json={"versao": work["versao"]}).status_code == 409
    reviewed = client.post(url + "/evidencias/conferir", json={"versao": work["versao"]}).json()
    calls = []
    def fake_draft(**kwargs):
        calls.append(kwargs)
        return MinutaGerada(contexto_consolidado="Contexto", analise_providencia="Conferir", minuta="Minuta para revisão", confianca=0.5)
    monkeypatch.setattr(work_service, "draft_peticao", fake_draft)
    response = client.post(url + "/minuta", json={"versao": reviewed["versao"]})
    assert response.status_code == 200, response.text
    petition = db_session.get(models.Peticao, response.json()["peticao_id"])
    assert petition.dossie["origem"] == "trabalho" and petition.prazo_id is None
    assert petition.dossie["evidencias"]["conferida_por"]
    assert calls[0]["source_kind"] == "trabalho" and calls[0]["prazo_fatal"] is None
    assert counts == (db_session.query(models.Intimacao).count(), db_session.query(models.Prazo).count())


def test_changed_documents_invalidate_evidence_review(client, db_session, seeded, monkeypatch):
    work = prepared_work(client, db_session, seeded, monkeypatch)
    context = db_session.query(models.ContextoProcesso).order_by(models.ContextoProcesso.id.desc()).first()
    context.source_fingerprint = "outdated"
    db_session.commit()
    response = client.post(f"/trabalhos/{work['id']}/evidencias/conferir", json={"versao": work["versao"]})
    assert response.status_code == 409


def test_edit_during_model_call_does_not_publish_stale_evidence(client, db_session, seeded, monkeypatch):
    from app.agent import work_service
    work = prepared_work(client, db_session, seeded, monkeypatch)
    def racing_analysis(**kwargs):
        row = db_session.get(models.TrabalhoJuridico, work["id"])
        row.instrucoes = "Objetivo alterado durante a chamada"
        row.versao += 1
        db_session.commit()
        return {"fatos": [], "cronologia": [], "contradicoes": [], "lacunas": []}
    monkeypatch.setattr(work_service, "analyze_sources", racing_analysis)
    result = client.post(f"/trabalhos/{work['id']}/evidencias", json={"versao": work["versao"]})
    assert result.status_code == 409


def test_scope_is_explicit_and_versioned(client, db_session, seeded):
    work = client.post("/trabalhos", json={"processo_id": seeded.id, "providencia": "Conferir autos"}).json()
    payload = {"versao": work["versao"], "data_referencia": "2026-09-01", "declaracao": "Recebi os documentos disponibilizados pelo advogado."}
    first = client.put(f"/trabalhos/{work['id']}/escopo", json=payload)
    assert first.status_code == 200, first.text
    assert first.json()["escopo"]["origem"] == "declaracao_advogado"
    assert first.json()["escopo"]["usuario_id"]
    assert client.put(f"/trabalhos/{work['id']}/escopo", json=payload).status_code == 409


def test_gap_task_is_linked_deduplicated_and_version_checked(client, db_session, seeded, monkeypatch):
    work = prepared_work(client, db_session, seeded, monkeypatch)
    url = f"/trabalhos/{work['id']}/lacunas/0/tarefa"
    first = client.post(url, json={"versao": work["versao"]})
    assert first.status_code == 200
    assert client.post(url, json={"versao": work["versao"]}).json()["id"] == first.json()["id"]
    task = client.get(f"/tarefas/{first.json()['id']}").json()
    assert task["trabalho_id"] == work["id"] and task["origem"] == "lacuna_trabalho"
    assert client.post(url, json={"versao": work["versao"] - 1}).status_code == 409


def test_missing_scope_blocks_analysis_without_calling_provider(client, seeded, monkeypatch):
    from app.agent import work_service
    monkeypatch.setattr(work_service, "analyze_sources", lambda **kw: (_ for _ in ()).throw(AssertionError("provider called")))
    work = client.post("/trabalhos", json={"processo_id": seeded.id, "providencia": "Manifestação"}).json()
    response = client.post(f"/trabalhos/{work['id']}/evidencias", json={"versao": work["versao"]})
    assert response.status_code == 409 and "escopo" in response.text


def test_linked_notice_and_sor_history_reach_analysis(client, db_session, seeded, monkeypatch):
    from app.agent import work_service
    notice = db_session.query(models.Intimacao).filter_by(processo_id=seeded.id).first()
    old = models.Intimacao(processo_id=seeded.id, escritorio_id=seeded.escritorio_id,
                           fonte="DJEN", fonte_id="old", teor="Decisão anterior")
    prior = models.Peticao(processo_id=seeded.id, escritorio_id=seeded.escritorio_id,
                           tipo="Defesa", conteudo="Pedido anterior", status="rascunho",
                           dossie={"trabalho_id": "manual"})
    foreign_office = models.Escritorio(nome="Outro escritório")
    db_session.add(foreign_office)
    db_session.flush()
    foreign = models.Peticao(processo_id=seeded.id, escritorio_id=foreign_office.id,
                             tipo="Defesa", conteudo="Conteúdo de outro tenant", status="rascunho")
    foreign_notice = models.Intimacao(processo_id=seeded.id, escritorio_id=foreign_office.id,
                                      fonte="DJEN", fonte_id="foreign", teor="Comunicação de outro tenant")
    db_session.add_all([old, prior, foreign, foreign_notice])
    db_session.commit()
    work = prepared_work(client, db_session, seeded, monkeypatch, linked=True)
    captured = []
    queries = []
    select_original = work_service.select_evidence
    def select_with_query(*args, **kwargs):
        queries.append(kwargs["query"])
        return select_original(*args, **kwargs)
    def analyze(**kwargs):
        captured.append(kwargs)
        return {"fatos": [], "cronologia": [], "contradicoes": [], "lacunas": []}
    monkeypatch.setattr(work_service, "select_evidence", select_with_query)
    monkeypatch.setattr(work_service, "analyze_sources", analyze)
    response = client.post(f"/trabalhos/{work['id']}/evidencias", json={"versao": work["versao"]})
    assert response.status_code == 200, response.text
    assert notice.teor in captured[0]["evidence_text"]
    assert notice.teor in queries[0]
    assert captured[0]["evidence_text"].count(notice.teor) == 1
    assert "Decisão anterior" in captured[0]["evidence_text"]
    assert "Pedido anterior" in captured[0]["evidence_text"]
    assert "Conteúdo de outro tenant" not in captured[0]["evidence_text"]
    assert "Comunicação de outro tenant" not in captured[0]["evidence_text"]
    assert response.json()["evidencias"]["source_snapshot"]["dados"]["comunicacao"]["fonte_id"] == notice.fonte_id


def test_notice_edit_during_analysis_rejects_result(client, db_session, seeded, monkeypatch):
    from app.agent import work_service
    work = prepared_work(client, db_session, seeded, monkeypatch, linked=True)
    def racing(**kwargs):
        notice = db_session.get(models.Intimacao, work["intimacao_id"])
        notice.teor = "Teor corrigido durante a análise"
        db_session.commit()
        return {"fatos": [], "cronologia": [], "contradicoes": [], "lacunas": []}
    monkeypatch.setattr(work_service, "analyze_sources", racing)
    response = client.post(f"/trabalhos/{work['id']}/evidencias", json={"versao": work["versao"]})
    assert response.status_code == 409


@pytest.mark.parametrize("change", ["metadata", "history"])
def test_process_metadata_and_history_edits_during_analysis_reject_result(client, db_session, seeded, monkeypatch, change):
    from app.agent import work_service
    work = prepared_work(client, db_session, seeded, monkeypatch, linked=True)
    def racing(**kwargs):
        if change == "metadata":
            process = db_session.get(models.Processo, seeded.id)
            process.orgao_julgador = "Vara corrigida"
        else:
            db_session.add(models.Intimacao(processo_id=seeded.id, escritorio_id=seeded.escritorio_id,
                                             fonte="DJEN", fonte_id="new-history", teor="Novo ato anterior"))
        db_session.commit()
        return {"fatos": [], "cronologia": [], "contradicoes": [], "lacunas": []}
    monkeypatch.setattr(work_service, "analyze_sources", racing)
    response = client.post(f"/trabalhos/{work['id']}/evidencias", json={"versao": work["versao"]})
    assert response.status_code == 409


def test_notice_edit_after_review_rejects_draft(client, db_session, seeded, monkeypatch):
    from app.agent import work_service
    work = prepared_work(client, db_session, seeded, monkeypatch, linked=True)
    reviewed = client.post(f"/trabalhos/{work['id']}/evidencias/conferir",
                           json={"versao": work["versao"]}).json()
    notice = db_session.get(models.Intimacao, work["intimacao_id"])
    notice.teor = "Teor corrigido após conferência"
    db_session.commit()
    monkeypatch.setattr(work_service, "draft_peticao", lambda **kw: (_ for _ in ()).throw(AssertionError("draft called")))
    result = client.post(f"/trabalhos/{work['id']}/minuta", json={"versao": reviewed["versao"]})
    assert result.status_code == 409


def test_notice_edit_during_draft_rejects_without_petition(client, db_session, seeded, monkeypatch):
    from app.agent import work_service
    work = prepared_work(client, db_session, seeded, monkeypatch, linked=True)
    reviewed = client.post(f"/trabalhos/{work['id']}/evidencias/conferir",
                           json={"versao": work["versao"]}).json()
    before = db_session.query(models.Peticao).count()
    def racing(**kwargs):
        notice = db_session.get(models.Intimacao, work["intimacao_id"])
        notice.fonte_id = "corrected-origin"
        db_session.commit()
        return MinutaGerada(contexto_consolidado="", analise_providencia="", minuta="Obsoleta", confianca=0.5)
    monkeypatch.setattr(work_service, "draft_peticao", racing)
    result = client.post(f"/trabalhos/{work['id']}/minuta", json={"versao": reviewed["versao"]})
    assert result.status_code == 409
    assert db_session.query(models.Peticao).count() == before


def test_deadline_edit_during_draft_rejects_without_petition(client, db_session, seeded, monkeypatch):
    from app.agent import work_service
    work = prepared_work(client, db_session, seeded, monkeypatch, linked=True)
    reviewed = client.post(f"/trabalhos/{work['id']}/evidencias/conferir",
                           json={"versao": work["versao"]}).json()
    before = db_session.query(models.Peticao).count()
    seen = []
    def racing(**kwargs):
        seen.append(kwargs)
        deadline = db_session.get(models.Prazo, work["prazo_id"])
        deadline.dias = 16
        db_session.commit()
        return MinutaGerada(contexto_consolidado="", analise_providencia="", minuta="Obsoleta", confianca=0.5)
    monkeypatch.setattr(work_service, "draft_peticao", racing)
    result = client.post(f"/trabalhos/{work['id']}/minuta", json={"versao": reviewed["versao"]})
    assert result.status_code == 409
    assert seen[0]["prazo_confirmado"] is False
    assert db_session.query(models.Peticao).count() == before


def test_deadline_description_edit_during_draft_rejects_without_petition(client, db_session, seeded, monkeypatch):
    from app.agent import work_service
    work = prepared_work(client, db_session, seeded, monkeypatch, linked=True)
    reviewed = client.post(f"/trabalhos/{work['id']}/evidencias/conferir",
                           json={"versao": work["versao"]}).json()
    before = db_session.query(models.Peticao).count()
    def racing(**kwargs):
        deadline = db_session.get(models.Prazo, work["prazo_id"])
        deadline.descricao = "Nova descrição do ato"
        db_session.commit()
        return MinutaGerada(contexto_consolidado="", analise_providencia="", minuta="Obsoleta", confianca=0.5)
    monkeypatch.setattr(work_service, "draft_peticao", racing)
    result = client.post(f"/trabalhos/{work['id']}/minuta", json={"versao": reviewed["versao"]})
    assert result.status_code == 409
    assert db_session.query(models.Peticao).count() == before


def test_deadline_confirmation_keeps_source_analysis_current(client, db_session, seeded, monkeypatch):
    work = prepared_work(client, db_session, seeded, monkeypatch, linked=True)
    notice = db_session.get(models.Intimacao, work["intimacao_id"])
    notice.payload = {"_causor_prazo": {"status": "confirmado", "prazo_id": work["prazo_id"],
                                         "memoria_calculo": {"dias": 15}}}
    db_session.commit()
    result = client.post(f"/trabalhos/{work['id']}/evidencias/conferir", json={"versao": work["versao"]})
    assert result.status_code == 200, result.text


def test_repeated_own_draft_is_excluded_from_source_snapshot(client, db_session, seeded, monkeypatch):
    from app.agent import work_service
    work = prepared_work(client, db_session, seeded, monkeypatch, linked=True)
    source = work["evidencias"]["source_snapshot"]
    reviewed = client.post(f"/trabalhos/{work['id']}/evidencias/conferir",
                           json={"versao": work["versao"]}).json()
    monkeypatch.setattr(work_service, "draft_peticao", lambda **kw: MinutaGerada(
        contexto_consolidado="", analise_providencia="", minuta="Proposta anterior do modelo", confianca=0.5))
    drafted = client.post(f"/trabalhos/{work['id']}/minuta", json={"versao": reviewed["versao"]})
    assert drafted.status_code == 200, drafted.text
    second = client.post(f"/trabalhos/{work['id']}/evidencias", json={"versao": drafted.json()["versao"]})
    assert second.status_code == 200, second.text
    assert second.json()["evidencias"]["source_snapshot"] == source
    assert "Proposta anterior do modelo" not in second.json()["evidencias"]["texto"]


def test_long_sor_history_marks_individual_text_truncation(client, db_session, seeded, monkeypatch):
    db_session.add(models.Intimacao(processo_id=seeded.id, escritorio_id=seeded.escritorio_id,
                                   fonte="DJEN", fonte_id="long", teor="Trecho inicial " + "x" * 600))
    db_session.commit()
    work = prepared_work(client, db_session, seeded, monkeypatch, linked=True)
    assert "texto truncado após 500 caracteres" in work["evidencias"]["source_snapshot"]["dados"]["historico_sor"]


def test_provisional_deadline_is_explicit_in_drafter_prompt():
    from app.agent.classifier import ClassificacaoIntimacao
    from app.agent.drafter import draft_peticao
    class Provider:
        def __init__(self):
            self.prompt = ""
        def complete_structured(self, *, system, user, schema, max_tokens):
            self.prompt = user
            return schema(analise_providencia="Analisar", minuta="Texto", confianca=0.5)
    provider = Provider()
    classification = ClassificacaoIntimacao(tipo="Manifestação", peticao_sugerida="Manifestação",
                                            prazo_dias=15, dias_uteis=True, confianca=0, resumo="Revisar")
    result = draft_peticao(intimacao_texto="Pedido", classificacao=classification,
                           contexto_processo={}, prazo_fatal="2026-10-20", prazo_confirmado=False,
                           provider=provider, source_kind="trabalho")
    assert "PROVISÓRIO" in provider.prompt and "Não afirmar tempestividade" in provider.prompt
    assert "PROVISÓRIO" in result.contexto_consolidado
