"""Durable scheduling without contacting courts or the application database."""

from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.capture.scheduler import enqueue_due, enqueue_one
from app.queue.jobs import mark_failed, run_capture_oab_job
from app.sor import models
from tests.test_capture_scheduler import FakeDatajud, FakeDjen, _comunicacao
from app.prazo_engine.factory import build_calendar


NOW = datetime(2026, 10, 6, 1, tzinfo=timezone.utc)  # still 05/10 in Brazil


@pytest.fixture
def monitored(db_session):
    office = models.Escritorio(nome="Pilot")
    db_session.add(office)
    db_session.flush()
    row = models.OabMonitorada(escritorio_id=office.id, oab="12345", uf="SP")
    db_session.add(row)
    db_session.commit()
    return row


def test_enqueue_is_durable_bounded_brazil_day_and_restart_deduplicates(db_session, monitored):
    factory = sessionmaker(db_session.bind, expire_on_commit=False)
    assert enqueue_due(factory, now=NOW) == 1
    assert enqueue_due(factory, now=NOW) == 0
    job = db_session.scalar(select(models.JobExecucao))
    assert job.status == "queued"
    assert job.entidade_id == monitored.id
    assert job.payload["data_fim"] == "2026-10-05"
    assert job.payload["data_inicio"] == "2026-10-02"
    assert job.payload["enrich"] is False
    assert db_session.scalar(select(models.AuditLog.id)) is not None


@pytest.mark.parametrize("inactive,recent", [(True, False), (False, True)])
def test_inactive_and_not_due_are_skipped(db_session, monitored, inactive, recent):
    monitored.ativo = not inactive
    if recent:
        monitored.ultima_captura_em = NOW - timedelta(hours=11)
    db_session.commit()
    assert enqueue_one(db_session, monitored.id, monitored.escritorio_id, now=NOW) is None


def test_interval_boundary_and_active_manual_job(db_session, monitored, client):
    monitored.ultima_captura_em = NOW - timedelta(hours=12)
    db_session.commit()
    manual = client.post("/jobs/capture/oab", json={"oab": "12345", "uf": "SP"})
    assert manual.status_code == 200
    assert enqueue_one(db_session, monitored.id, monitored.escritorio_id, now=NOW) is None
    assert db_session.query(models.JobExecucao).count() == 1


def test_manual_reuses_scheduled_job_and_tenant_isolation(db_session, monitored, client):
    job = enqueue_one(db_session, monitored.id, monitored.escritorio_id, now=NOW)
    db_session.commit()
    response = client.post("/jobs/capture/oab", json={"oab": "12345", "uf": "SP"})
    assert response.status_code == 200
    assert response.json()["id"] == job.id
    other = models.Escritorio(nome="Other")
    db_session.add(other)
    db_session.flush()
    other_oab = models.OabMonitorada(escritorio_id=other.id, oab="12345", uf="SP")
    db_session.add(other_oab)
    db_session.commit()
    assert enqueue_one(db_session, other_oab.id, monitored.escritorio_id, now=NOW) is None
    assert enqueue_one(db_session, other_oab.id, other.id, now=NOW).id != job.id


def test_failure_cooldown_and_preserved_window_before_first_success(db_session, monitored):
    first = enqueue_one(db_session, monitored.id, monitored.escritorio_id, now=NOW)
    original_start = first.payload["data_inicio"]
    mark_failed(db_session, first, "source unavailable")
    first.updated_at = NOW
    db_session.commit()
    assert enqueue_one(db_session, monitored.id, monitored.escritorio_id, now=NOW) is None
    later = NOW + timedelta(days=9)
    retry = enqueue_one(db_session, monitored.id, monitored.escritorio_id, now=later)
    assert retry.payload["data_inicio"] == original_start
    assert retry.payload["data_fim"] == "2026-10-14"
    assert monitored.cursor_data is None
    assert monitored.ultima_captura_em is None


def test_success_advances_cursor_and_subsequent_window_keeps_overlap(db_session, monitored):
    monitored.cursor_data = date(2026, 9, 25)
    db_session.commit()
    job = enqueue_one(db_session, monitored.id, monitored.escritorio_id, now=NOW)
    assert job.payload["data_inicio"] == "2026-09-22"
    run_capture_oab_job(db_session, job.id, djen=FakeDjen([]), datajud=FakeDatajud(),
                        calendar=build_calendar([2026]))
    db_session.commit()
    db_session.refresh(monitored)
    assert monitored.cursor_data == date(2026, 10, 5)
    assert monitored.ultima_captura_em is not None
    at = monitored.ultima_captura_em.replace(tzinfo=timezone.utc) + timedelta(hours=12)
    next_job = enqueue_one(db_session, monitored.id, monitored.escritorio_id, now=at)
    assert next_job.payload["data_inicio"] == "2026-10-02"


@pytest.mark.parametrize("removed", [False, True])
def test_disabled_or_deleted_after_enqueue_never_contacts_source(db_session, monitored, removed):
    job = enqueue_one(db_session, monitored.id, monitored.escritorio_id, now=NOW)
    if removed:
        db_session.delete(monitored)
    else:
        monitored.ativo = False
    db_session.commit()
    djen = FakeDjen([_comunicacao()])
    from app.queue.jobs import JobError
    with pytest.raises(JobError):
        run_capture_oab_job(db_session, job.id, djen=djen, datajud=FakeDatajud(),
                            calendar=build_calendar([2026]))
    assert djen.calls == []


def test_partial_capture_failure_does_not_advance_cursor(db_session, monitored, monkeypatch):
    from app.capture.poll import PollResult
    from app.queue import jobs
    job = enqueue_one(db_session, monitored.id, monitored.escritorio_id, now=NOW)
    db_session.commit()
    monkeypatch.setattr(jobs, "poll_oab", lambda *a, **k: PollResult(djen_indisponivel=True))
    run_capture_oab_job(db_session, job.id, djen=FakeDjen([]), datajud=FakeDatajud(),
                        calendar=build_calendar([2026]), batch_days=1,
                        commit_each=lambda s: s.commit())
    assert job.status == "failed"
    assert monitored.cursor_data is None
    assert monitored.ultima_captura_em is None


def test_scheduler_settings_are_positive():
    from pydantic import ValidationError
    from app.settings import Settings
    for key in ("capture_scheduler_tick_seconds", "capture_failure_cooldown_seconds"):
        with pytest.raises(ValidationError):
            Settings(**{key: 0}, _env_file=None)


def test_scheduler_worker_notice_and_deadline_pipeline(db_session, monitored, monkeypatch):
    from app.agent.deadline_interpretation import DeadlineInterpretation
    from app.queue.worker import WorkerClients, run_once
    from app.prazo_engine.pipeline import KEY
    from app.settings import settings

    monkeypatch.setattr(settings, "datajud_api_key", "")
    factory = sessionmaker(db_session.bind, expire_on_commit=False)
    at = datetime(2024, 9, 10, 12, tzinfo=timezone.utc)
    assert enqueue_due(factory, now=at) == 1
    clients = WorkerClients(djen=FakeDjen([_comunicacao()]), datajud=FakeDatajud(),
                            calendar=build_calendar([2024, 2025]),
                            deadline_interpreter=lambda text: DeadlineInterpretation(
                                status="prazo", regime="cpc_civel_djen", dias=15,
                                unidade="dias_uteis", termo="publicacao_djen",
                                evidencia="manifestar em 15 dias", confianca=.98))
    assert run_once(factory, clients=clients, batch_days=15, commit_each=lambda s: s.commit()) == 1
    # Analysis jobs created during capture belong to the next finite worker batch.
    assert run_once(factory, clients=clients) == 1
    db_session.expire_all()
    notice = db_session.scalar(select(models.Intimacao))
    assert notice.escritorio_id == monitored.escritorio_id
    assert notice.payload[KEY]["status"] == "calculado_a_revisar"
    assert db_session.scalar(select(models.Prazo.id)) is not None
    assert enqueue_due(factory, now=at) == 0


def test_capture_failed_between_windows_cannot_be_resurrected(db_session, monitored):
    from app.queue.jobs import JobError
    job = enqueue_one(db_session, monitored.id, monitored.escritorio_id, now=NOW)
    db_session.commit()
    djen = FakeDjen([])

    def interruption(session):
        session.commit()
        mark_failed(session, job, "worker interrupted")
        session.commit()

    with pytest.raises(JobError):
        run_capture_oab_job(db_session, job.id, djen=djen, datajud=FakeDatajud(),
                            calendar=build_calendar([2026]), batch_days=1,
                            commit_each=interruption)
    assert job.status == "failed"
    assert len(djen.calls) == 1
    assert monitored.cursor_data is None
