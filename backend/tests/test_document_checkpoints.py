from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
from threading import Event

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.autos import leases, worker
from app.autos.summarizer import ChunkCitation, DocumentDigest
from app.sor import models
from tests.test_autos_upload_api import local_store as local_store
from tests.postgres.test_postgres_flows import (
    test_document_restart_preserves_transaction_and_reuses_completed_extraction as test_document_restart_preserves_transaction_and_reuses_completed_extraction,
)


@pytest.mark.parametrize("lost_at", [None, "extraction", "summary"])
def test_io_runs_without_sessions_and_stale_results_cannot_publish(
    client, db_session, seeded, local_store, monkeypatch, lost_at,
):
    pdf = (Path(__file__).parent / "fixtures/pdfs/textual.pdf").read_bytes()
    assert client.post(f"/processos/{seeded.id}/autos/upload", data={"grau": "1"},
                       files=[("arquivos", ("autos.pdf", pdf, "application/pdf"))]).status_code == 200
    open_sessions = []

    class TrackedSession(Session):
        def __enter__(self):
            open_sessions.append(self)
            return super().__enter__()

        def __exit__(self, *args):
            super().__exit__(*args)
            open_sessions.remove(self)

    factory = sessionmaker(bind=db_session.get_bind(), class_=TrackedSession, expire_on_commit=False)
    new_token = []

    def probe(stage):
        assert not open_sessions, "OCR/provider must not hold even a read session"
        # Independent connection can lock the job/version during expensive work.
        with factory() as session:
            job = session.scalar(select(models.JobExecucao).where(
                models.JobExecucao.tipo == "process_document",
            ).with_for_update(nowait=True))
            session.scalar(select(models.DocumentoArquivo).with_for_update(nowait=True))
            if stage == lost_at:
                job.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
                session.commit()
                worker.recover_stale_document_jobs(session, older_than_minutes=60)
                replacement = worker.claim_due_processing_jobs(session, limit=1)[0]
                new_token.append(replacement.lease_token)
                session.commit()

    real_extract = worker.extract_pdf_pages

    def extract(data):
        probe("extraction")
        return real_extract(data)

    class Provider:
        def complete_structured(self, *, user, **kwargs):
            probe("summary")
            chunk_id = int(re.search(r"chunk_id=(\d+)", user).group(1))
            quote = user.split("]\n", 1)[1].split("\n\n[chunk_id=", 1)[0][:60]
            return DocumentDigest(resumo="Citado", fatos=[], pedidos=[], decisoes=[], prazos=[],
                                  incertezas=[], citations=[ChunkCitation(chunk_id=chunk_id, quote=quote)])

    monkeypatch.setattr(worker, "extract_pdf_pages", extract)
    monkeypatch.setattr("app.autos.summarizer.get_provider", lambda **kwargs: Provider())
    assert worker.process_due_documents(factory) == 1
    db_session.expire_all()
    job = db_session.scalar(select(models.JobExecucao).where(models.JobExecucao.tipo == "process_document"))
    if lost_at:
        assert job.status == "running" and job.lease_token == new_token[0]
        assert db_session.scalar(select(models.DocumentoResumo)) is None
        assert bool(db_session.scalar(select(models.DocumentoTrecho))) is (lost_at == "summary")
        assert db_session.scalar(select(models.ContextoProcesso).where(models.ContextoProcesso.status == "ready")) is None
    else:
        assert job.status == "completed" and job.lease_token is None and job.lease_expires_at is None
        assert db_session.scalar(select(models.DocumentoResumo)).status == "complete"


def test_background_heartbeat_renews_with_its_own_short_session(db_session, monkeypatch):
    job = models.JobExecucao(tipo="process_document", status="queued")
    db_session.add(job)
    db_session.commit()
    monkeypatch.setattr(leases.settings, "document_lease_seconds", 1)
    job = worker.claim_due_processing_jobs(db_session, limit=1)[0]
    job_id, token, previous = job.id, job.lease_token, job.lease_expires_at
    db_session.commit()
    db_session.close()
    factory = sessionmaker(bind=db_session.get_bind(), expire_on_commit=False)
    done = Event()
    real_renew = leases.renew_lease

    def renew(*args):
        result = real_renew(*args)
        done.set()
        return result

    monkeypatch.setattr(leases, "renew_lease", renew)
    with leases.Heartbeat(factory, job_id, token) as heartbeat:
        assert done.wait(5), "background renewal did not run"
        heartbeat.check()
    with factory() as session:
        expiry = session.get(models.JobExecucao, job_id).lease_expires_at
        assert expiry.replace(tzinfo=timezone.utc) > previous
        assert worker.recover_stale_document_jobs(session, older_than_minutes=60) == []
