from datetime import datetime, timedelta, timezone

import pytest

from app.autos.worker import recover_stale_document_jobs
from app.queue.jobs import fail_stale_running_jobs
from app.sor import models


def test_recovery_only_requeues_old_document_jobs_and_audits(db_session, seeded):
    now = datetime.now(timezone.utc)
    old = now - timedelta(hours=2)
    jobs = [models.JobExecucao(tipo=kind, status=status, updated_at=when,
                              payload={"escritorio_id": seeded.escritorio_id})
            for kind, status, when in [
                ("process_document", "running", old),
                ("process_document", "running", now),
                ("process_document", "failed", old),
                ("protocolo", "running", old),
                ("mni_capture", "running", old),
            ]]
    db_session.add_all(jobs)
    db_session.flush()
    assert recover_stale_document_jobs(db_session, older_than_minutes=60, now=now) == [jobs[0]]
    assert [j.status for j in jobs] == ["queued", "running", "failed", "running", "running"]
    event = db_session.query(models.AuditLog).filter_by(acao="document_job_recovered").one()
    assert event.entidade_id == jobs[0].id
    assert event.escritorio_id == seeded.escritorio_id


def test_generic_stale_cleanup_cannot_change_document_or_filing_jobs(db_session):
    old = datetime.now(timezone.utc) - timedelta(hours=2)
    jobs = [models.JobExecucao(tipo=kind, status="running", updated_at=old)
            for kind in ("captura_oab", "process_document", "protocolo", "mni_capture")]
    db_session.add_all(jobs)
    db_session.flush()
    assert fail_stale_running_jobs(db_session, older_than_minutes=60) == [jobs[0]]
    assert all(j.status == "running" for j in jobs[1:])


def test_recovery_rejects_nonpositive_age(db_session):
    with pytest.raises(ValueError):
        recover_stale_document_jobs(db_session, older_than_minutes=0)
