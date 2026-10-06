"""Real enqueue/removal row locks in an explicitly disposable schema."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Barrier

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.capture.scheduler import enqueue_due
from app.sor import models
from tests.postgres.test_postgres_capture_concurrency import _client
from tests.test_scheduled_capture import (  # noqa: F401
    test_success_advances_cursor_and_subsequent_window_keeps_overlap,
    test_failure_cooldown_and_preserved_window_before_first_success,
    monitored,
)


def _seed(engine):
    with Session(engine) as session:
        office = models.Escritorio(nome="Pilot")
        session.add(office)
        session.flush()
        row = models.OabMonitorada(escritorio_id=office.id, oab="12345", uf="SP")
        session.add(row)
        session.commit()
        return office.id, row.id


def test_two_schedulers_and_manual_request_create_one_active_job(pg_engine):
    office_id, _ = _seed(pg_engine)
    factory = sessionmaker(pg_engine, expire_on_commit=False)
    barrier = Barrier(3)

    def run(kind):
        barrier.wait()
        if kind == "manual":
            response = _client(pg_engine, office_id).post("/jobs/capture/oab",
                                                         json={"oab": "12345", "uf": "SP"})
            assert response.status_code == 200
            return 0
        return enqueue_due(factory, now=datetime.now(timezone.utc))

    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(run, ["scheduler", "scheduler", "manual"]))
    assert sum(results) <= 1
    with Session(pg_engine) as session:
        jobs = list(session.scalars(select(models.JobExecucao).where(
            models.JobExecucao.tipo == "captura_oab")))
        assert len(jobs) == 1
        assert jobs[0].status == "queued"


def test_enqueue_racing_removal_does_not_leave_executable_capture(pg_engine):
    office_id, oab_id = _seed(pg_engine)
    factory = sessionmaker(pg_engine, expire_on_commit=False)
    barrier = Barrier(2)

    def run(kind):
        barrier.wait()
        if kind == "remove":
            response = _client(pg_engine, office_id).delete(f"/capturas/oab/{oab_id}")
            assert response.status_code == 200
        else:
            enqueue_due(factory)

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(run, ["remove", "scheduler"]))
    with Session(pg_engine) as session:
        assert session.get(models.OabMonitorada, oab_id) is None
        for job in session.scalars(select(models.JobExecucao).where(models.JobExecucao.tipo == "captura_oab")):
            from app.queue.jobs import JobError, _lock_capture_job
            import pytest
            with pytest.raises(JobError):
                _lock_capture_job(session, job.id)
