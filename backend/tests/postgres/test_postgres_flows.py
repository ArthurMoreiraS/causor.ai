"""Reuse the public workflow with PostgreSQL migrations and real transactions."""

from pathlib import Path
import re

import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.autos.summarizer import ChunkCitation, DocumentDigest
from app.autos.worker import process_due_documents
from app.sor import models
from tests.test_audit_preservation import (
    test_oab_cleanup_preserves_existing_audit as test_oab_cleanup_preserves_existing_audit,
    test_reseeding_demo_preserves_previous_events as test_reseeding_demo_preserves_previous_events,
)
from tests.test_autos_upload_api import (
    local_store as local_store,
    test_upload_worker_builds_context_and_retry_preserves_summary as test_upload_worker_builds_context_and_retry_preserves_summary,
)


@pytest.mark.parametrize("crash", [True, False])
def test_document_restart_preserves_transaction_and_reuses_completed_extraction(
    client, db_session, seeded, local_store, monkeypatch, crash,
):
    from app.autos import worker

    pdf = (Path(__file__).parents[1] / "fixtures/pdfs/textual.pdf").read_bytes()
    response = client.post(f"/processos/{seeded.id}/autos/upload", data={"grau": "1"},
                           files=[("arquivos", ("autos.pdf", pdf, "application/pdf"))])
    assert response.status_code == 200
    extraction_calls = []
    real_extract = worker.extract_pdf_pages

    def extract(data):
        extraction_calls.append(1)
        return real_extract(data)

    class Provider:
        calls = 0

        def complete_structured(self, *, user, **kw):
            self.calls += 1
            if self.calls == 1:
                if crash:
                    raise SystemExit("simulated worker death")
                raise RuntimeError("simulated provider outage")
            chunk_id = int(re.search(r"chunk_id=(\d+)", user).group(1))
            quote = user.split("]\n", 1)[1].split("\n\n[chunk_id=", 1)[0][:60]
            return DocumentDigest(resumo="Citado", fatos=[], pedidos=[], decisoes=[], prazos=[],
                                  incertezas=[], citations=[ChunkCitation(chunk_id=chunk_id, quote=quote)])

    provider = Provider()
    monkeypatch.setattr(worker, "extract_pdf_pages", extract)
    monkeypatch.setattr("app.autos.summarizer.get_provider", lambda **kw: provider)
    factory = sessionmaker(bind=db_session.get_bind(), expire_on_commit=False)
    if crash:
        with pytest.raises(SystemExit):
            process_due_documents(factory)
    else:
        assert process_due_documents(factory) == 1
    db_session.expire_all()
    job = db_session.scalars(select(models.JobExecucao).where(models.JobExecucao.tipo == "process_document")).one()
    assert job.status == ("queued" if crash else "failed")
    before_ids = set(db_session.scalars(select(models.DocumentoTrecho.id)))
    assert bool(before_ids) is (not crash)
    if not crash:
        assert client.post(f"/processos/{seeded.id}/autos/reprocessar").status_code == 200
    assert process_due_documents(factory) == 1
    db_session.expire_all()
    assert db_session.get(models.JobExecucao, job.id).status == "completed"
    assert len(extraction_calls) == (2 if crash else 1)
    if not crash:
        assert before_ids == set(db_session.scalars(select(models.DocumentoTrecho.id)))
