from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import sessionmaker

from app.autos.leases import LeaseLost, guard_lease, renew_lease
from app.autos.worker import claim_due_processing_jobs, recover_stale_document_jobs
from app.sor import models
from app.storage.objects import LocalObjectStore


def test_expired_owner_cannot_renew_or_publish_after_reclaim(db_session, tmp_path):
    store = LocalObjectStore(tmp_path)
    job = models.JobExecucao(tipo="process_document", status="queued", payload={"store_id": store.store_id})
    db_session.add(job)
    db_session.commit()
    claimed = claim_due_processing_jobs(db_session, limit=1, object_store=store)[0]
    old_token = claimed.lease_token
    job_id = claimed.id
    assert old_token and claimed.lease_expires_at
    db_session.commit()
    factory = sessionmaker(bind=db_session.get_bind(), expire_on_commit=False)
    assert renew_lease(factory, job_id, old_token)
    db_session.expire_all()
    claimed.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_session.commit()
    assert not renew_lease(factory, job_id, old_token)
    with pytest.raises(LeaseLost):
        guard_lease(db_session, job_id, old_token)
    db_session.rollback()
    assert len(recover_stale_document_jobs(db_session, older_than_minutes=60, object_store=store)) == 1
    new_owner = claim_due_processing_jobs(db_session, limit=1, object_store=store)[0]
    assert new_owner.lease_token != old_token
    db_session.commit()
    assert not renew_lease(factory, job_id, old_token)
    with pytest.raises(LeaseLost):
        guard_lease(db_session, job_id, old_token)
    db_session.rollback()
    assert guard_lease(db_session, job_id, new_owner.lease_token).status == "running"


def test_fresh_lease_is_not_recovered_by_old_updated_at(db_session):
    now = datetime.now(timezone.utc)
    job = models.JobExecucao(
        tipo="process_document", status="running", lease_token="active",
        lease_expires_at=now + timedelta(minutes=2), updated_at=now - timedelta(hours=2),
    )
    db_session.add(job)
    db_session.flush()
    assert recover_stale_document_jobs(db_session, older_than_minutes=60, now=now) == []
    assert claim_due_processing_jobs(db_session) == []


def test_document_lease_never_renews_filing_job(db_session):
    job = models.JobExecucao(
        tipo="protocolo", status="running", lease_token="foreign",
        lease_expires_at=datetime.now(timezone.utc) + timedelta(minutes=2),
    )
    db_session.add(job)
    db_session.commit()
    factory = sessionmaker(bind=db_session.get_bind())
    assert not renew_lease(factory, job.id, "foreign")


def test_tagged_job_with_missing_bytes_remains_claimable_and_observable(db_session, tmp_path):
    store = LocalObjectStore(tmp_path)
    job = models.JobExecucao(tipo="process_document", status="queued",
                            payload={"store_id": store.store_id, "documento_arquivo_id": 999999})
    db_session.add(job)
    db_session.flush()
    assert claim_due_processing_jobs(db_session, object_store=store) == [job]
    assert job.status == "running"


def test_own_job_is_found_after_multiple_pages_of_foreign_jobs(db_session, tmp_path):
    own = LocalObjectStore(tmp_path / "own")
    foreign = LocalObjectStore(tmp_path / "foreign")
    db_session.add_all([
        models.JobExecucao(tipo="process_document", status="queued",
                           payload={"store_id": foreign.store_id}) for _ in range(205)
    ])
    own_job = models.JobExecucao(tipo="process_document", status="queued",
                                 payload={"store_id": own.store_id})
    db_session.add(own_job)
    db_session.flush()
    assert claim_due_processing_jobs(db_session, limit=1, object_store=own) == [own_job]
