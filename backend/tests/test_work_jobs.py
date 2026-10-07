"""Persistent work jobs with simulated providers and a local database."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy.orm import sessionmaker

from app.agent.drafter import MinutaGerada
from app.queue.work_leases import heartbeat_once, owned_job
from app.queue.worker import WorkerClients, claim_next_job, run_once
from app.sor import models
from tests.test_legal_work import prepared_work
from tests.test_autos_upload_api import local_store  # noqa: F401


class _Noop:
    def consultar(self, *args, **kwargs):
        return []

    def consultar_processo(self, *args, **kwargs):
        return None


def _factory(db_session):
    return sessionmaker(bind=db_session.bind, autoflush=False, expire_on_commit=False)


def _request(client, work, action="analise", request_id=None, **extra):
    return client.post(f"/trabalhos/{work['id']}/operacoes", json={
        "acao": action, "versao": work["versao"], "request_id": request_id or str(uuid4()), **extra})


def test_enqueue_is_short_idempotent_and_terminal_retry_does_not_redraft(client, db_session, seeded, monkeypatch):
    from app.agent import work_service

    work = prepared_work(client, db_session, seeded, monkeypatch, linked=True)
    reviewed = client.post(f"/trabalhos/{work['id']}/evidencias/conferir",
                           json={"versao": work["versao"]}).json()
    calls = []
    monkeypatch.setattr(work_service, "draft_peticao", lambda **kw: (
        calls.append(kw) or MinutaGerada(contexto_consolidado="", analise_providencia="",
                                          minuta="Minuta simulada", confianca=0.5)))
    key = str(uuid4())
    alias = str(uuid4())
    queued = _request(client, reviewed, "minuta", key)
    assert queued.status_code == 202, queued.text
    assert queued.json()["status"] == "queued" and not calls
    assert "payload" not in queued.json()
    assert _request(client, reviewed, "minuta", key).json()["id"] == queued.json()["id"]
    assert _request(client, reviewed, "minuta", alias).json()["id"] == queued.json()["id"]
    factory = _factory(db_session)
    from app.prazo_engine.factory import build_calendar
    clients = WorkerClients(djen=_Noop(), datajud=_Noop(), calendar=build_calendar([2026]))
    assert run_once(factory, clients=clients) == 1
    done = client.get(f"/trabalhos/{work['id']}/operacoes/{queued.json()['id']}")
    assert done.status_code == 200 and done.json()["status"] == "completed"
    assert done.json()["resultado"]["peticao_id"]
    assert _request(client, reviewed, "minuta", key).json()["id"] == queued.json()["id"]
    assert _request(client, reviewed, "minuta", alias).json()["id"] == queued.json()["id"]
    assert len(calls) == 1 and db_session.query(models.Peticao).count() == 1
    assert db_session.query(models.AuditLog).filter_by(acao="minuta_gerada").count() == 1


def test_request_key_divergence_and_queued_input_change(client, db_session, seeded, monkeypatch):
    work = prepared_work(client, db_session, seeded, monkeypatch, linked=True)
    key = str(uuid4())
    first = _request(client, work, request_id=key, perguntas=["Questão original"])
    assert first.status_code == 202, first.text
    assert _request(client, work, request_id=key, perguntas=["Outra questão"]).status_code == 409
    notice = db_session.get(models.Intimacao, work["intimacao_id"])
    notice.teor = "Teor corrigido na fila"
    db_session.commit()
    from app.prazo_engine.factory import build_calendar
    clients = WorkerClients(djen=_Noop(), datajud=_Noop(), calendar=build_calendar([2026]))
    assert run_once(_factory(db_session), clients=clients) == 1
    job = client.get(f"/trabalhos/{work['id']}/operacoes/{first.json()['id']}").json()
    assert job["status"] == "failed" and "Teor corrigido" not in str(job)


def test_source_change_between_claim_and_service_is_rejected(client, db_session, seeded, monkeypatch):
    from app.queue import work_jobs
    work = prepared_work(client, db_session, seeded, monkeypatch, linked=True)
    queued = _request(client, work)
    original = work_jobs.prepare_work_evidence
    def change_before_service(session, **kwargs):
        notice = session.get(models.Intimacao, work["intimacao_id"])
        notice.teor = "Mudança entre validação e execução"
        session.commit()
        return original(session, **kwargs)
    monkeypatch.setattr(work_jobs, "prepare_work_evidence", change_before_service)
    from app.prazo_engine.factory import build_calendar
    clients = WorkerClients(djen=_Noop(), datajud=_Noop(), calendar=build_calendar([2026]))
    assert run_once(_factory(db_session), clients=clients) == 1
    job = client.get(f"/trabalhos/{work['id']}/operacoes/{queued.json()['id']}").json()
    assert job["status"] == "failed"
    assert db_session.get(models.TrabalhoJuridico, work["id"]).versao == work["versao"]


def test_final_lease_fence_rolls_back_domain_and_job(client, db_session, seeded, monkeypatch):
    from app.queue import work_jobs
    work = prepared_work(client, db_session, seeded, monkeypatch, linked=True)
    reviewed = client.post(f"/trabalhos/{work['id']}/evidencias/conferir",
                           json={"versao": work["versao"]}).json()
    queued = _request(client, reviewed, "minuta")
    from app.agent import work_service
    monkeypatch.setattr(work_service, "draft_peticao", lambda **kw: MinutaGerada(
        contexto_consolidado="", analise_providencia="", minuta="Não publicar", confianca=0.5))
    actual_guard = work_jobs.owned_job
    calls = 0
    def expire_at_final_flush(session, job_id, token):
        nonlocal calls
        calls += 1
        return None if calls == 4 else actual_guard(session, job_id, token)
    monkeypatch.setattr(work_jobs, "owned_job", expire_at_final_flush)
    from app.prazo_engine.factory import build_calendar
    clients = WorkerClients(djen=_Noop(), datajud=_Noop(), calendar=build_calendar([2026]))
    assert run_once(_factory(db_session), clients=clients) == 1
    assert db_session.query(models.Peticao).count() == 0
    db_session.expire_all()
    assert db_session.get(models.JobExecucao, queued.json()["id"]).status == "running"


def test_job_reads_are_private_to_requesting_user(client, db_session, seeded, monkeypatch):
    from app.auth.jwt_auth import CurrentUser, get_current_user
    work = prepared_work(client, db_session, seeded, monkeypatch)
    queued = _request(client, work)
    another = models.Usuario(escritorio_id=seeded.escritorio_id, email="outro@teste.invalid", nome="Outro")
    db_session.add(another)
    db_session.commit()
    client.app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        usuario_id=another.id, escritorio_id=seeded.escritorio_id, email=another.email)
    assert client.get(f"/trabalhos/{work['id']}/operacoes/atual").json() is None
    assert client.get(f"/trabalhos/{work['id']}/operacoes/{queued.json()['id']}").status_code == 404


def test_lease_recovery_and_old_owner_cannot_complete(db_session):
    job = models.JobExecucao(tipo="minuta_trabalho", status="queued", entidade="trabalho_juridico",
                             entidade_id=1, payload={})
    db_session.add(job)
    db_session.commit()
    first = claim_next_job(db_session)
    old_token = first.lease_token
    assert heartbeat_once(_factory(db_session), job.id, old_token)
    first.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_session.commit()
    second = claim_next_job(db_session)
    assert second.id == first.id and second.lease_token != old_token
    assert owned_job(db_session, job.id, old_token) is None
    assert heartbeat_once(_factory(db_session), job.id, old_token) is False
    assert heartbeat_once(_factory(db_session), job.id, second.lease_token) is True


def test_new_interactive_work_precedes_remaining_deadline_batch(db_session):
    first = models.JobExecucao(tipo="analise_prazo", status="queued")
    second = models.JobExecucao(tipo="analise_prazo", status="queued")
    db_session.add_all([first, second])
    db_session.commit()
    max_id = second.id
    assert claim_next_job(db_session, max_id=max_id).id == first.id
    interactive = models.JobExecucao(tipo="minuta_trabalho", status="queued")
    db_session.add(interactive)
    db_session.commit()
    assert claim_next_job(db_session, max_id=max_id).id == interactive.id
    assert claim_next_job(db_session, max_id=max_id).id == second.id


def test_dispatch_uses_token_captured_at_claim_even_if_row_changes(db_session, monkeypatch):
    from app.queue import worker
    from app.prazo_engine.factory import build_calendar
    job = models.JobExecucao(tipo="minuta_trabalho", status="queued", payload={})
    db_session.add(job)
    db_session.commit()
    original_get = worker.get_job
    seen = []

    def swapped(session, job_id):
        row = original_get(session, job_id)
        row.lease_token = str(uuid4())
        seen.append(row.lease_token)
        session.commit()
        return row

    monkeypatch.setattr(worker, "get_job", swapped)
    monkeypatch.setattr(worker, "run_work_job", lambda _session, _factory, _id, token: seen.append(token))
    clients = WorkerClients(djen=_Noop(), datajud=_Noop(), calendar=build_calendar([2026]))
    assert run_once(_factory(db_session), clients=clients) == 1
    assert len(seen) == 2 and seen[0] != seen[1]


def test_claim_keeps_original_token_across_postcommit_refresh(db_session, monkeypatch):
    from sqlalchemy.orm import sessionmaker
    job = models.JobExecucao(tipo="minuta_trabalho", status="queued", payload={})
    db_session.add(job)
    db_session.commit()
    factory = sessionmaker(bind=db_session.bind, autoflush=False, expire_on_commit=True)
    with factory() as session:
        original_refresh = session.refresh
        replaced = []

        def refresh_after_reclaim(row):
            with factory() as competing:
                successor = competing.get(models.JobExecucao, row.id)
                successor.lease_token = str(uuid4())
                replaced.append(successor.lease_token)
                competing.commit()
            original_refresh(row)

        monkeypatch.setattr(session, "refresh", refresh_after_reclaim)
        claimed = claim_next_job(session)
        assert claimed._claimed_lease_token != replaced[0]
        assert claimed.lease_token == replaced[0]


@pytest.mark.usefixtures("local_store")
def test_http_upload_context_analysis_review_draft_edit_and_resume(
    client, db_session, seeded, monkeypatch,
):
    from pathlib import Path
    import re
    from app.agent import work_service
    from app.autos.summarizer import ChunkCitation, DocumentDigest
    from app.autos.worker import process_due_documents
    from app.capture.djen import ComunicacaoDTO
    from app.prazo_engine.factory import build_calendar
    from app.prazo_engine.pipeline import run_analysis
    from app.queue.jobs import mark_running
    from tests.test_deadline_capture_integration import _capture, _interpret

    office = db_session.get(models.Escritorio, seeded.escritorio_id)
    item = ComunicacaoDTO.from_item({"id": "work-flow-notice", "numero_processo": seeded.numero,
        "siglaTribunal": "TJSP", "tipoComunicacao": "Intimação",
        "nomeClasse": "Procedimento Comum Cível",
        "texto": "Intima-se a parte ré para manifestar em 5 dias úteis.",
        "data_disponibilizacao": "2026-09-25"})
    assert _capture(db_session, office, item).intimacoes_novas == 1
    notice = db_session.query(models.Intimacao).filter_by(fonte_id="work-flow-notice").one()
    deadline_job = db_session.query(models.JobExecucao).filter_by(
        tipo="analise_prazo", entidade_id=notice.id).one()
    mark_running(db_session, deadline_job)
    db_session.commit()
    run_analysis(db_session, deadline_job, interpreter=_interpret)
    deadline = db_session.query(models.Prazo).filter_by(intimacao_id=notice.id).one()
    assert deadline.revisao_status == "calculado_a_revisar"

    customer = models.Cliente(escritorio_id=seeded.escritorio_id, nome="Parte representada")
    db_session.add(customer)
    db_session.flush()
    seeded.cliente_id = customer.id
    db_session.commit()

    class SummaryProvider:
        def complete_structured(self, *, user, **_):
            chunk_id = int(re.search(r"chunk_id=(\d+)", user).group(1))
            quote = user.split("]\n", 1)[1].split("\n\n[chunk_id=", 1)[0][:60]
            return DocumentDigest(resumo="Autos simulados", fatos=[], pedidos=[], decisoes=[],
                prazos=[], incertezas=[], citations=[ChunkCitation(chunk_id=chunk_id, quote=quote)])

    monkeypatch.setattr("app.autos.summarizer.get_provider", lambda **_: SummaryProvider())
    pdf = (Path(__file__).parent / "fixtures/pdfs/textual.pdf").read_bytes()
    upload = client.post(f"/processos/{seeded.id}/autos/upload", data={"grau": "1"},
        files=[("arquivos", ("autos.pdf", pdf, "application/pdf"))])
    assert upload.status_code == 200, upload.text
    declaration = client.post(f"/processos/{seeded.id}/autos/nao-aplicavel", json={
        "grau": "2", "justificativa": "Conferência simulada: não há autos em segundo grau para este teste."})
    assert declaration.status_code == 200, declaration.text
    factory = _factory(db_session)
    assert process_due_documents(factory, backoff_seconds=0) == 1
    db_session.expire_all()
    assert client.get(f"/processos/{seeded.id}/autos/status").json()["contexto"]["ready"] is True

    created = client.post("/trabalhos", json={"processo_id": seeded.id, "providencia": "Manifestação",
        "polo": "Autor", "intimacao_id": notice.id, "prazo_id": deadline.id})
    assert created.status_code == 201, created.text
    work = created.json()
    scoped = client.put(f"/trabalhos/{work['id']}/escopo", json={"versao": work["versao"],
        "data_referencia": "2026-09-01", "declaracao": "Autos sintéticos recebidos e conferidos para este teste."})
    assert scoped.status_code == 200, scoped.text
    work = scoped.json()
    observed = []
    def analyze(**kwargs):
        observed.append(kwargs["evidence_text"])
        return {"fatos": [], "cronologia": [], "contradicoes": [], "lacunas": ["Conferir assinatura"]}
    monkeypatch.setattr(work_service, "analyze_sources", analyze)
    monkeypatch.setattr(work_service, "draft_peticao", lambda **_: MinutaGerada(
        contexto_consolidado="Autos simulados", analise_providencia="Revisar",
        minuta="Minuta simulada para revisão", confianca=0.5))
    clients = WorkerClients(djen=_Noop(), datajud=_Noop(), calendar=build_calendar([2026]))
    analysis_key = str(uuid4())
    analysis = _request(client, work, "analise", analysis_key, perguntas=["Há comprovante?"])
    assert analysis.status_code == 202 and analysis.json()["status"] == "queued"
    assert run_once(factory, clients=clients) == 1
    resumed = client.get(f"/trabalhos/{work['id']}/operacoes/atual").json()
    assert resumed["id"] == analysis.json()["id"] and resumed["status"] == "completed"
    analyzed = client.get(f"/trabalhos/{work['id']}").json()
    assert notice.teor in observed[0] and "Autos simulados" in observed[0]
    reviewed = client.post(f"/trabalhos/{work['id']}/evidencias/conferir",
        json={"versao": analyzed["versao"]})
    assert reviewed.status_code == 200, reviewed.text
    draft_key = str(uuid4())
    drafting = _request(client, reviewed.json(), "minuta", draft_key)
    assert drafting.status_code == 202 and drafting.json()["status"] == "queued"
    assert run_once(factory, clients=clients) == 1
    done = client.get(f"/trabalhos/{work['id']}/operacoes/{drafting.json()['id']}").json()
    assert done["status"] == "completed" and done["resultado"]["peticao_id"]
    petition = db_session.get(models.Peticao, done["resultado"]["peticao_id"])
    assert petition.dossie["source_snapshot"]["dados"]["comunicacao"]["fonte_id"] == "work-flow-notice"
    assert petition.dossie["prazo_snapshot"]["id"] == deadline.id
    assert _request(client, reviewed.json(), "minuta", draft_key).json()["id"] == done["id"]
    edited = client.patch(f"/peticoes/{done['resultado']['peticao_id']}", json={
        "conteudo": "Texto revisado pelo advogado"})
    assert edited.status_code == 200 and edited.json()["conteudo"] == "Texto revisado pelo advogado"


def test_resposta_truncada_do_modelo_aparece_como_tal_e_nao_como_fontes_alteradas(client, db_session, seeded, monkeypatch):
    from app.agent.llm import LLMProviderError
    from app.queue import work_jobs
    from app.prazo_engine.factory import build_calendar

    work = prepared_work(client, db_session, seeded, monkeypatch, linked=True)
    queued = _request(client, work)

    def truncated(session, **kwargs):
        raise LLMProviderError("A resposta do modelo veio incompleta ou fora do formato esperado")
    monkeypatch.setattr(work_jobs, "prepare_work_evidence", truncated)
    clients = WorkerClients(djen=_Noop(), datajud=_Noop(), calendar=build_calendar([2026]))
    assert run_once(_factory(db_session), clients=clients) == 1
    job = client.get(f"/trabalhos/{work['id']}/operacoes/{queued.json()['id']}").json()
    assert job["status"] == "failed"
    assert job["erro"] == "A resposta do modelo veio incompleta ou fora do formato esperado. Tente novamente"


def test_analise_exige_cliente_e_polo_antes_de_comecar(client, db_session, seeded, monkeypatch):
    work = prepared_work(client, db_session, seeded, monkeypatch, linked=False)
    seeded.cliente_id = None
    db_session.commit()
    response = _request(client, work)
    assert response.status_code == 409
    assert "Vincule o cliente" in response.json()["detail"]
