"""Production scheduler: queue due captures, heartbeat only after a full tick."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
import signal
from threading import Event
import time

from app.capture.scheduler import enqueue_due
from app.settings import settings
from app.sor.db import SessionLocal

logger = logging.getLogger(__name__)
HEARTBEAT = Path("/tmp/causor-capture-scheduler.heartbeat")


def healthy(path: Path = HEARTBEAT, *, now: float | None = None, tick: float | None = None) -> bool:
    try:
        age = (time.time() if now is None else now) - path.stat().st_mtime
        interval = settings.capture_scheduler_tick_seconds if tick is None else tick
        return 0 <= age <= max(60, interval * 3)
    except OSError:
        return False


def run_loop(session_factory=SessionLocal, *, stop: Event | None = None,
             heartbeat: Path = HEARTBEAT, tick: float | None = None, enqueue=enqueue_due) -> None:
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
        return 0
    stop = Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    run_loop(stop=stop)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
