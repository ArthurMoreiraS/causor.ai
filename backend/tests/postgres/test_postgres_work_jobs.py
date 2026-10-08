"""Disposable PostgreSQL concurrency for work-job creation and ownership."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event, current_thread
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.work_routes import WorkOperationIn, create_work_operation
from app.auth.jwt_auth import CurrentUser
from app.sor import models
from tests.test_legal_work import prepared_work
from tests.test_work_jobs import (  # noqa: F401
    test_enqueue_is_short_idempotent_and_terminal_retry_does_not_redraft,
    test_request_key_divergence_and_queued_input_change,
    test_source_change_between_claim_and_service_is_rejected,
)


def test_old_provider_owner_cannot_publish_after_lease_reclaim(client, db_session, seeded, pg_engine, monkeypatch):
    from datetime import datetime, timedelta, timezone
    from sqlalchemy.orm import sessionmaker
    from app.agent import work_service
    from app.agent.drafter import MinutaGerada
    from app.queue import work_jobs
    from app.queue.worker import claim_next_job

    work = prepared_work(client, db_session, seeded, monkeypatch, linked=True)
    reviewed = client.post(f"/trabalhos/{work['id']}/evidencias/conferir",
                           json={"versao": work["versao"]}).json()
    queued = client.post(f"/trabalhos/{work['id']}/operacoes", json={
        "acao": "minuta", "versao": reviewed["versao"], "request_id": str(uuid4())})
    assert queued.status_code == 202, queued.text
    db_session.commit()
    factory = sessionmaker(bind=pg_engine, autoflush=False, expire_on_commit=False)
    entered, release = Event(), Event()

    class NoHeartbeat:
        def __init__(self, *_):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *_):
            pass

    def draft(**_):
        if current_thread().name.startswith("old-owner"):
            entered.set()
            assert release.wait(timeout=8)
            text = "Minuta obsoleta"
        else:
            text = "Minuta do novo dono"
        return MinutaGerada(contexto_consolidado="", analise_providencia="", minuta=text, confianca=0.5)

    monkeypatch.setattr(work_jobs, "LeaseHeartbeat", NoHeartbeat)
    monkeypatch.setattr(work_service, "draft_peticao", draft)
    with factory() as session:
        first = claim_next_job(session)
        old_token = first.lease_token

    def old_execution():
        with factory() as session:
            return work_jobs.run_work_job(session, factory, queued.json()["id"], old_token)

    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="old-owner") as pool:
        future = pool.submit(old_execution)
        try:
            assert entered.wait(timeout=8)
            with factory() as session:
                job = session.get(models.JobExecucao, queued.json()["id"])
                job.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
                session.commit()
            with factory() as session:
                second = claim_next_job(session)
                assert second.id == queued.json()["id"] and second.lease_token != old_token
                new_token = second.lease_token
            with factory() as session:
                assert work_jobs.run_work_job(session, factory, queued.json()["id"], new_token)
        finally:
            release.set()
        assert future.result(timeout=8) is False

    db_session.expire_all()
    petition = db_session.scalar(select(models.Peticao).where(models.Peticao.processo_id == seeded.id))
    job = db_session.get(models.JobExecucao, queued.json()["id"])
    assert petition.conteudo == "Minuta do novo dono"
    assert job.status == "completed" and job.resultado["peticao_id"] == petition.id
    assert db_session.scalar(select(func.count()).select_from(models.Peticao).where(
        models.Peticao.processo_id == seeded.id)) == 1


def test_concurrent_same_request_creates_one_work_job(client, db_session, seeded, pg_engine, monkeypatch):
    work = prepared_work(client, db_session, seeded, monkeypatch)
    user = db_session.scalar(select(models.Usuario).where(models.Usuario.escritorio_id == seeded.escritorio_id))
    principal = CurrentUser(usuario_id=user.id, escritorio_id=user.escritorio_id, email=user.email, papel="administrador")
    db_session.commit()
    barrier = Barrier(2)
    request_id = uuid4()

    def enqueue(_):
        with Session(pg_engine, autoflush=False, expire_on_commit=False) as session:
            barrier.wait(timeout=5)
            result = create_work_operation(work["id"], WorkOperationIn(
                acao="analise", versao=work["versao"], request_id=request_id), session, principal)
            return result["id"]

    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(pool.map(enqueue, range(2)))
    assert ids[0] == ids[1]
    db_session.expire_all()
    assert db_session.scalar(select(func.count()).select_from(models.JobExecucao).where(
        models.JobExecucao.entidade == "trabalho_juridico",
        models.JobExecucao.entidade_id == work["id"])) == 1
