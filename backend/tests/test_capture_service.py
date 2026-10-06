"""Scheduler liveness and shutdown without real sleeps or database calls."""

import os

import pytest

from app.capture.service import healthy, run_loop


class StopAfter:
    def __init__(self, ticks):
        self.ticks = ticks
        self.waits = []

    def is_set(self):
        return len(self.waits) >= self.ticks

    def wait(self, interval):
        self.waits.append(interval)


def test_empty_tick_is_healthy_and_shutdown_wait_is_interruptible(tmp_path):
    heartbeat = tmp_path / "heartbeat"
    stop = StopAfter(1)
    run_loop(object(), stop=stop, heartbeat=heartbeat, tick=10, enqueue=lambda _: 0)
    assert healthy(heartbeat, now=heartbeat.stat().st_mtime, tick=10)
    assert stop.waits == [10]
    assert not healthy(heartbeat, now=heartbeat.stat().st_mtime + 61, tick=10)


def test_failure_survives_but_does_not_refresh_health_or_log_secrets(tmp_path, caplog):
    heartbeat = tmp_path / "heartbeat"
    heartbeat.touch()
    stop = StopAfter(2)
    calls = []

    def enqueue(_):
        calls.append(1)
        raise RuntimeError("database password: should never be logged")

    run_loop(object(), stop=stop, heartbeat=heartbeat, tick=10, enqueue=enqueue)
    assert len(calls) == 2
    assert not heartbeat.exists()
    assert "password" not in caplog.text
    assert "RuntimeError" in caplog.text


def test_recovery_creates_heartbeat_only_after_completed_tick(tmp_path):
    heartbeat = tmp_path / "heartbeat"
    stop = StopAfter(2)
    calls = []

    def enqueue(_):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("unavailable")
        assert not heartbeat.exists()
        return 1

    run_loop(object(), stop=stop, heartbeat=heartbeat, tick=10, enqueue=enqueue)
    assert heartbeat.exists()
    os.utime(heartbeat, (100, 100))
    assert healthy(heartbeat, now=100, tick=300)
    assert not healthy(heartbeat, now=1001, tick=300)


def test_nonpositive_tick_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        run_loop(object(), heartbeat=tmp_path / "heartbeat", tick=0)
