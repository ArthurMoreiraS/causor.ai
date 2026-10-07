"""Production scheduler: queue due captures, heartbeat only after a full tick.

Each tick also closes the loop after capture without anyone clicking: analyses
left behind (never run, outdated, failed) are queued again, and deadline
notices are delivered by e-mail when SMTP is configured.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import logging
from pathlib import Path
import signal
from threading import Event
import time
from zoneinfo import ZoneInfo

from app.alertas.notificacao import notificar_prazos
from app.alertas.senders import build_sender
from app.capture.scheduler import enqueue_due
from app.prazo_engine.pipeline import requeue_analyses
from app.settings import settings
from app.sor.db import SessionLocal

logger = logging.getLogger(__name__)
HEARTBEAT = Path("/tmp/causor-capture-scheduler.heartbeat")
SAO_PAULO = ZoneInfo("America/Sao_Paulo")
# Avisos fora deste horário esperam o próximo ciclo dentro dele.
NOTIFY_HOURS = range(7, 21)


def automation_tick(session_factory=SessionLocal, *, now: datetime | None = None,
                    sender_factory=build_sender) -> dict:
    """Reanalisa o que ficou para trás e entrega os avisos de prazo."""
    now = now or datetime.now(timezone.utc)
    with session_factory() as session:
        queued = requeue_analyses(session)
        session.commit()
    sent = 0
    local = now.astimezone(SAO_PAULO)
    # Sem SMTP o aviso seria só log, e auditar "simulado" a cada ciclo polui a trilha.
    if settings.smtp_host and local.hour in NOTIFY_HOURS:
        with session_factory() as session:
            sent = len(notificar_prazos(session, sender=sender_factory(), hoje=local.date()))
            session.commit()
    return {"reanalises": queued, "avisos": sent}


def healthy(path: Path = HEARTBEAT, *, now: float | None = None, tick: float | None = None) -> bool:
    try:
        age = (time.time() if now is None else now) - path.stat().st_mtime
        interval = settings.capture_scheduler_tick_seconds if tick is None else tick
        return 0 <= age <= max(60, interval * 3)
    except OSError:
        return False


def run_loop(session_factory=SessionLocal, *, stop: Event | None = None,
             heartbeat: Path = HEARTBEAT, tick: float | None = None, enqueue=enqueue_due,
             automate=automation_tick) -> None:
    interval = settings.capture_scheduler_tick_seconds if tick is None else tick
    if interval <= 0:
        raise ValueError("tick must be positive")
    stop = stop or Event()
    # A restart must not inherit the previous process's healthy heartbeat.
    heartbeat.unlink(missing_ok=True)
    while not stop.is_set():
        try:
            count = enqueue(session_factory)
            heartbeat.touch()
            logger.info("capture scheduler tick completed: queued=%s", count)
        except Exception as exc:
            # Driver exceptions may contain SQL parameters/connection secrets.
            logger.error("capture scheduler tick failed: %s", type(exc).__name__)
        # Separate step: a notice failure never stops capture or its heartbeat.
        try:
            outcome = automate(session_factory)
            logger.info("deadline automation completed: %s", outcome)
        except Exception as exc:
            logger.error("deadline automation failed: %s", type(exc).__name__)
        stop.wait(interval)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--healthcheck", action="store_true")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args(argv)
    if args.healthcheck:
        return 0 if healthy() else 1
    logging.basicConfig(level=logging.INFO)
    if args.once:
        count = enqueue_due(SessionLocal)
        HEARTBEAT.touch()
        logger.info("capture scheduler tick completed: queued=%s", count)
        logger.info("deadline automation completed: %s", automation_tick())
        return 0
    stop = Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    run_loop(stop=stop)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
