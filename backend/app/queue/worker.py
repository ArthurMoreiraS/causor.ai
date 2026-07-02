"""In-process job worker — drains queued jobs off the API/CLI request thread.

This is the MVP executor: a single local loop that claims the oldest queued
job, marks it running, dispatches by ``tipo`` and commits. It exists so a heavy
``captura_oab`` (e.g. 180-day manual lookback) runs in the background while the
API returns a ``queued`` job immediately (see ``POST /jobs/capture/oab``).

The database contract (``JobExecucao.status`` queued -> running -> completed |
failed + audit) is intentionally the same shape a Redis/RQ worker will update
later. Replacing this loop with RQ must not change ``run_capture_oab_job`` nor
the API surface — only the claim/dispatch plumbing here.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.capture.datajud import DatajudClient
from app.capture.djen import DjenClient
from app.prazo_engine.calendar import ForensicCalendar
from app.prazo_engine.factory import build_calendar
from app.queue.jobs import get_job, mark_failed, run_capture_oab_job
from app.settings import settings
from app.sor import models
from app.sor.db import SessionLocal


def _utcnow_naive() -> date:
    return date.today()


@dataclass(frozen=True)
class WorkerClients:
    djen: DjenClient
    datajud: DatajudClient
    calendar: ForensicCalendar


def default_clients(today: date | None = None) -> WorkerClients:
    """Build the real production clients used by the worker."""
    year = (today or _utcnow_naive()).year
    return WorkerClients(
        djen=DjenClient(),
        datajud=DatajudClient() if settings.datajud_api_key else _NoopDatajudClient(),
        calendar=build_calendar([year - 1, year, year + 1]),
    )


class _NoopDatajudClient:
    """DataJud stand-in when no API key is configured: returns nothing, never throws."""

    def consultar_processo(self, numero_processo: str, *, tribunal: str):  # noqa: ANN001
        return None


def claim_next_job(session: Session) -> models.JobExecucao | None:
    """Claim the oldest queued job: select it, mark running, and commit.

    Single-worker MVP: no SKIP LOCKED. Redis/RQ replaces this claim entirely.
    """
    job = session.scalars(
        select(models.JobExecucao)
        .where(models.JobExecucao.status == "queued")
        .order_by(models.JobExecucao.id)
        .limit(1)
    ).first()
    if job is None:
        return None
    job.status = "running"
    session.commit()
    session.refresh(job)
    return job


def dispatch(
    session: Session,
    job: models.JobExecucao,
    clients: WorkerClients,
    *,
    batch_days: int | None = None,
    commit_each: Callable[[Session], None] | None = None,
) -> None:
    """Execute one job by tipo. Captures domain failures as ``failed``.

    ``commit_each`` is forwarded to ``run_capture_oab_job`` so a windowed capture
    commits per batch (progressive, visible via ``GET /jobs/{id}``).
    """
    if job.tipo == "captura_oab":
        payload = job.payload or {}
        data_inicio = _parse_date(payload.get("data_inicio"))
        data_fim = _parse_date(payload.get("data_fim"))
        run_capture_oab_job(
            session,
            job.id,
            djen=clients.djen,
            datajud=clients.datajud,
            calendar=clients.calendar,
            dias_default=int(payload.get("dias_default", 15)),
            data_inicio=data_inicio,
            data_fim=data_fim,
            batch_days=batch_days,
            commit_each=commit_each,
        )
        session.commit()
        return

    mark_failed(session, job, f"tipo de job nao suportado pelo worker: {job.tipo}")
    session.commit()


def _parse_date(value: object) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def run_once(
    session_factory: sessionmaker,
    *,
    clients: WorkerClients,
    batch_days: int | None = None,
    commit_each: Callable[[Session], None] | None = None,
) -> int:
    """Drain all currently-queued jobs. Returns the number of jobs processed."""
    processed = 0
    while True:
        session = session_factory()
        try:
            job = claim_next_job(session)
        finally:
            session.close()
        if job is None:
            return processed
        processed += 1
        session = session_factory()
        try:
            job = get_job(session, job.id)
            dispatch(
                session,
                job,
                clients,
                batch_days=batch_days,
                commit_each=commit_each,
            )
        except Exception as exc:  # worker must not die on a single bad job
            session.rollback()
            session = session_factory()
            try:
                job = get_job(session, job.id)
                mark_failed(session, job, str(exc)[:2000])
                session.commit()
            except Exception:
                session.rollback()
            finally:
                session.close()
        else:
            session.close()


def run_loop(
    session_factory: sessionmaker,
    *,
    clients_factory: Callable[[], WorkerClients] = default_clients,
    batch_days: int | None = None,
    commit_each: Callable[[Session], None] | None = None,
    idle_seconds: float = 2.0,
    sleeper: Callable[[float], None] = time.sleep,
) -> int:
    """Block forever, polling for queued jobs. Returns only on KeyboardInterrupt.

    ``clients`` are built once upfront; each job gets a fresh session.
    """
    clients = clients_factory()
    effective_batch = settings.capture_batch_days if batch_days is None else batch_days
    while True:
        processed = run_once(
            session_factory,
            clients=clients,
            batch_days=effective_batch,
            commit_each=commit_each,
        )
        if processed == 0:
            sleeper(idle_seconds)


__all__ = [
    "WorkerClients",
    "claim_next_job",
    "default_clients",
    "dispatch",
    "run_loop",
    "run_once",
]


if __name__ == "__main__":  # pragma: no cover
    run_loop(SessionLocal)