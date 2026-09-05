"""Real migration, locking and crash-recovery contracts (no court/LLM calls)."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.autos.context import build_process_context
from app.autos.worker import claim_due_processing_jobs, recover_stale_document_jobs
from app.queue.worker import claim_next_job
from app.sor import models
from tests.postgres.conftest import migrate


def _jobs(engine, kinds=("process_document", "process_document", "captura_oab"), status="queued"):
    with Session(engine) as session:
        jobs = [models.JobExecucao(tipo=kind, status=status,
                 updated_at=datetime.now(timezone.utc) - timedelta(hours=2)) for kind in kinds]
        session.add_all(jobs)
        session.flush()
        ids = [j.id for j in jobs]
        session.commit()
    return ids


def test_full_migration_chain_matches_model_columns(pg_engine):
    inspector = inspect(pg_engine)
    for table in models.Base.metadata.sorted_tables:
        assert {c.name for c in table.columns} == {c["name"] for c in inspector.get_columns(table.name)}
    with pg_engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "a5f1b7d3c9e2"
        assert connection.scalar(text("SELECT tgenabled FROM pg_trigger WHERE tgname = 'audit_log_append_only' AND tgrelid = 'audit_log'::regclass")) == "A"


@pytest.mark.parametrize("sql", [
    "UPDATE audit_log SET acao = 'changed'", "DELETE FROM audit_log", "TRUNCATE audit_log",
])
def test_audit_mutations_fail_in_database_and_preserve_original(pg_engine, sql):
    with Session(pg_engine) as session:
        session.add(models.AuditLog(ator="test", acao="original", detalhe={"hash": "original"}))
        session.commit()
    with pytest.raises(DBAPIError, match="append-only"):
        with pg_engine.begin() as connection:
            connection.execute(text(sql))
    with pg_engine.connect() as connection:
        assert connection.scalar(text("SELECT acao FROM audit_log")) == "original"


def test_audit_guard_downgrade_and_reupgrade_preserve_events(pg_engine):
    with Session(pg_engine) as session:
        session.add(models.AuditLog(ator="test", acao="preserved"))
        session.commit()
    migrate(pg_engine, "a3e7b1c9d2f8", downgrade=True)
    migrate(pg_engine)
    with pg_engine.connect() as connection:
        assert connection.scalar(text("SELECT acao FROM audit_log")) == "preserved"
    with pytest.raises(DBAPIError, match="append-only"):
        with pg_engine.begin() as connection:
            connection.execute(text("DELETE FROM audit_log"))


def test_two_consumers_claim_different_documents_and_oab_stays_separate(pg_engine):
    ids = _jobs(pg_engine)
    with Session(pg_engine) as first, Session(pg_engine) as second, Session(pg_engine) as oab:
        assert claim_due_processing_jobs(first, limit=1)[0].id == ids[0]
        assert claim_due_processing_jobs(second, limit=1)[0].id == ids[1]
        assert claim_next_job(oab).id == ids[2]
        assert claim_due_processing_jobs(oab, limit=1) == []


def test_killed_database_connection_releases_claim_for_restart(pg_engine):
    ids = _jobs(pg_engine, kinds=("process_document",))
    session = Session(pg_engine)
    try:
        pid = session.scalar(text("SELECT pg_backend_pid()"))
        assert claim_due_processing_jobs(session, limit=1)[0].id == ids[0]
        with pg_engine.begin() as killer:
            assert killer.scalar(text("SELECT pg_terminate_backend(:pid, 1000)"), {"pid": pid})
        session.invalidate()
        with Session(pg_engine) as restarted:
            assert claim_due_processing_jobs(restarted, limit=1)[0].id == ids[0]
    finally:
        session.invalidate()
        session.close()


def test_stale_recovery_skips_locked_jobs_and_never_touches_filing(pg_engine):
    ids = _jobs(pg_engine, kinds=("process_document", "process_document", "protocolo"), status="running")
    with Session(pg_engine) as active, Session(pg_engine) as recovery:
        active.execute(select(models.JobExecucao).where(models.JobExecucao.id == ids[0]).with_for_update())
        recovered = recover_stale_document_jobs(recovery, older_than_minutes=60)
        assert [j.id for j in recovered] == [ids[1]]
        recovery.commit()
        assert active.get(models.JobExecucao, ids[0]).status == "running"
        assert active.get(models.JobExecucao, ids[2]).status == "running"
        assert recovery.scalars(select(models.AuditLog).where(models.AuditLog.acao == "document_job_recovered")).one().entidade_id == ids[1]


def test_context_publication_is_serialized_and_idempotent(pg_engine):
    with Session(pg_engine) as session:
        office = models.Escritorio(nome="Postgres test")
        session.add(office)
        session.flush()
        process = models.Processo(escritorio_id=office.id, numero="00000010020248260100")
        session.add(process)
        session.flush()
        process_id = process.id
        session.commit()

    def publish():
        with Session(pg_engine) as session:
            context = build_process_context(session, processo=session.get(models.Processo, process_id))
            context_id = context.id
            session.commit()
            return context_id

    with ThreadPoolExecutor(max_workers=2) as executor:
        ids = list(executor.map(lambda _: publish(), range(2)))
    assert ids[0] == ids[1]
