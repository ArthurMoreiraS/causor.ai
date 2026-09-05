"""Document-only ownership. All writes are fenced by token and expiry.

OCR and provider calls run without a database session. A separate heartbeat
uses short transactions; after loss, results cannot be committed by this owner.
This module must never recover/retry a court filing.
"""

from datetime import datetime, timedelta, timezone
import logging
from threading import Event, Thread

from sqlalchemy import func, select

from app.settings import settings
from app.sor import models


class LeaseLost(RuntimeError):
    pass


def database_now(session) -> datetime:
    # PostgreSQL now() is transaction-start time, unsuitable after a lock wait.
    if session.get_bind().dialect.name == "postgresql":
        return session.scalar(select(func.clock_timestamp()))
    return datetime.now(timezone.utc)


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def check_expiry(session, job) -> None:
    """Recheck after checkpoint work/lock waits, while the caller holds the job lock."""
    if job.lease_expires_at is None or _utc(job.lease_expires_at) <= database_now(session):
        raise LeaseLost("document_lease_lost")


def guard_lease(session, job_id: int, token: str) -> models.JobExecucao:
    job = session.scalar(select(models.JobExecucao).where(
        models.JobExecucao.id == job_id,
    ).with_for_update().execution_options(populate_existing=True))
    now = database_now(session)
    if (job is None or job.tipo != "process_document" or job.status != "running"
            or not token or job.lease_token != token or job.lease_expires_at is None
            or _utc(job.lease_expires_at) <= now):
        raise LeaseLost("document_lease_lost")
    return job


def renew_lease(session_factory, job_id: int, token: str) -> bool:
    with session_factory() as session:
        try:
            job = guard_lease(session, job_id, token)
        except LeaseLost:
            return False
        job.lease_expires_at = database_now(session) + timedelta(seconds=settings.document_lease_seconds)
        session.commit()
        return True


class Heartbeat:
    def __init__(self, session_factory, job_id: int, token: str):
        self.factory, self.job_id, self.token = session_factory, job_id, token
        self.stop = Event()
        self.lost = Event()
        self.thread = Thread(target=self._run, daemon=True, name=f"document-lease-{job_id}")

    def _run(self):
        while not self.stop.wait(settings.document_lease_seconds / 3):
            try:
                if renew_lease(self.factory, self.job_id, self.token):
                    continue
            except Exception:
                logging.getLogger(__name__).warning("document_heartbeat_failed job_id=%s", self.job_id)
            self.lost.set()
            return

    def check(self):
        if self.lost.is_set():
            raise LeaseLost("document_lease_lost")

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.stop.set()
        self.thread.join(timeout=5)
