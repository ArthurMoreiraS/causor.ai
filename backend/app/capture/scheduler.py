"""Schedule and run capture cycles for monitored OAB registrations.

Windows-friendly: o comando CLI ``capture-due`` (cron / Agendador de Tarefas)
dispara o executor in-process. O contrato de job não muda, então um worker
Redis/RQ pode substituir o executor depois sem tocar nesta camada.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.capture.datajud import DatajudClient
from app.capture.djen import DjenClient
from app.prazo_engine.calendar import ForensicCalendar
from app.queue.jobs import create_job, run_capture_oab_job
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
