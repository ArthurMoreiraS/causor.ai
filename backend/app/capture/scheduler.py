"""Schedule and run capture cycles for monitored OAB registrations.

Windows-friendly: o comando CLI ``capture-due`` (cron / Agendador de Tarefas)
dispara o executor in-process. O contrato de job não muda, então um worker
Redis/RQ pode substituir o executor depois sem tocar nesta camada.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.capture.datajud import DatajudClient
from app.capture.djen import DjenClient
from app.prazo_engine.calendar import ForensicCalendar
from app.queue.jobs import create_job, mark_failed, run_capture_oab_job
from app.settings import settings
from app.sor import models


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def select_due(session: Session, *, now: datetime | None = None) -> list[models.OabMonitorada]:
    """Active monitored OABs whose last capture is older than their interval."""
    now = now or _utcnow()
    stmt = select(models.OabMonitorada).where(models.OabMonitorada.ativo.is_(True))
    due: list[models.OabMonitorada] = []
    for oab in session.scalars(stmt):
        if oab.ultima_captura_em is None:
            due.append(oab)
            continue
        proxima = _as_aware(oab.ultima_captura_em) + timedelta(hours=oab.intervalo_horas)
        if proxima <= now:
            due.append(oab)
    return due


def run_capture_for_oab(
    session: Session,
    oab: models.OabMonitorada,
    *,
    djen: DjenClient,
    datajud: DatajudClient,
    calendar: ForensicCalendar,
    today: date | None = None,
    now: datetime | None = None,
) -> models.JobExecucao:
    """Create and run one capture job for a monitored OAB, advancing its cursor."""
    today = today or date.today()
    now = now or _utcnow()
    lookback = timedelta(days=settings.capture_lookback_days)
    base = oab.cursor_data or today
    data_inicio = base - lookback

    job = create_job(
        session,
        tipo="captura_oab",
        entidade="oab_monitorada",
        entidade_id=oab.id,
        payload={
            "oab": oab.oab,
            "uf": oab.uf,
            "escritorio_id": oab.escritorio_id,
            "data_inicio": data_inicio.isoformat(),
            "data_fim": today.isoformat(),
        },
    )
    job = run_capture_oab_job(
        session,
        job.id,
        djen=djen,
        datajud=datajud,
        calendar=calendar,
        data_inicio=data_inicio,
        data_fim=today,
    )
    oab.ultima_captura_em = now
    oab.cursor_data = today
    return job


@dataclass(frozen=True)
class ResilientCaptureResult:
    job: models.JobExecucao
    attempts: int
    succeeded: bool


RETRYABLE_CAPTURE_ERRORS = (httpx.HTTPError, OperationalError)


def run_capture_for_oab_resilient(
    session: Session,
    oab: models.OabMonitorada,
    *,
    djen: DjenClient,
    datajud: DatajudClient,
    calendar: ForensicCalendar,
    max_attempts: int | None = None,
    backoff_seconds: float | None = None,
    sleeper: Callable[[float], None] = time.sleep,
    today: date | None = None,
    now: datetime | None = None,
) -> ResilientCaptureResult:
    """Run and commit one scheduled capture with bounded transient retries."""
    max_attempts = (
        settings.capture_retry_attempts if max_attempts is None else max_attempts
    )
    backoff_seconds = (
        settings.capture_retry_backoff_seconds
        if backoff_seconds is None
        else backoff_seconds
    )
    if max_attempts < 1:
        raise ValueError("max_attempts deve ser pelo menos 1")
    if backoff_seconds < 0:
        raise ValueError("backoff_seconds nao pode ser negativo")

    oab_id = oab.id
    label = {"oab": oab.oab, "uf": oab.uf, "escritorio_id": oab.escritorio_id}
    last_error: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        current = session.get(models.OabMonitorada, oab_id)
        if current is None:
            raise ValueError(f"OAB monitorada {oab_id} nao encontrada")
        try:
            job = run_capture_for_oab(
                session,
                current,
                djen=djen,
                datajud=datajud,
                calendar=calendar,
                today=today,
                now=now,
            )
            # poll_oab engole falhas transientes do DJEN (5xx/timeout apos os
            # retries internos do DjenClient) e retorna o parcial com
            # djen_indisponivel=True. Aceitamos o parcial como sucesso: o que
            # foi capturado fica salvo e o proximo ciclo agendado complementa
            # (dedup idempotente). Retentar imediatamente nao ajuda quando o
            # DJEN esta realmente fora; so adiciona carga. Erros transientes de
            # DB (OperationalError) ainda retentam pelo except abaixo.
            job.resultado = {**(job.resultado or {}), "tentativas": attempt}
            session.commit()
            return ResilientCaptureResult(job=job, attempts=attempt, succeeded=True)
        except RETRYABLE_CAPTURE_ERRORS as exc:
            session.rollback()
            last_error = exc
            if attempt < max_attempts:
                sleeper(backoff_seconds * (2 ** (attempt - 1)))
                continue
        except Exception as exc:  # non-transient domain/programming failure
            session.rollback()
            last_error = exc

        break

    assert last_error is not None
    job = create_job(
        session,
        tipo="captura_oab",
        entidade="oab_monitorada",
        entidade_id=oab_id,
        payload={**label, "tentativas": attempt},
    )
    mark_failed(session, job, str(last_error)[:2000])
    session.commit()
    return ResilientCaptureResult(job=job, attempts=attempt, succeeded=False)
