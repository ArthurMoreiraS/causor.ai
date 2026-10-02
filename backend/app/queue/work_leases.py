"""Renewable leases only for interactive legal-work analysis and drafting."""
from datetime import datetime, timedelta, timezone
from threading import Event, Thread

from sqlalchemy import func, select

from app.settings import settings
from app.sor import models

WORK_TYPES = ("analise_trabalho", "minuta_trabalho")


def database_now(session):
    if session.get_bind().dialect.name == "postgresql":
        return session.scalar(select(func.clock_timestamp()))
    return datetime.now(timezone.utc)


def _aware(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def owned_job(session, job_id: int, token: str):
    job = session.scalar(select(models.JobExecucao).where(
        models.JobExecucao.id == job_id).with_for_update().execution_options(populate_existing=True))
    if (job is None or job.tipo not in WORK_TYPES or job.status != "running" or
            job.lease_token != token or job.lease_expires_at is None or
            _aware(job.lease_expires_at) <= database_now(session)):
        return None
    return job


def heartbeat_once(session_factory, job_id: int, token: str) -> bool:
    with session_factory() as session:
        job = owned_job(session, job_id, token)
        if job is None:
            session.rollback()
            return False
        job.lease_expires_at = database_now(session) + timedelta(seconds=settings.work_job_lease_seconds)
        session.commit()
        return True


class LeaseHeartbeat:
    def __init__(self, session_factory, job_id: int, token: str):
        self.session_factory, self.job_id, self.token = session_factory, job_id, token
        self.stop = Event()
        self.thread = Thread(target=self._run, daemon=True, name=f"work-heartbeat-{job_id}")

    def _run(self):
        while not self.stop.wait(settings.work_job_heartbeat_seconds):
            try:
                if not heartbeat_once(self.session_factory, self.job_id, self.token):
                    return
            except Exception:
                # Publication checks expiry and token again; heartbeat errors cannot grant ownership.
                continue

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *_):
        self.stop.set()
        self.thread.join(timeout=2)
