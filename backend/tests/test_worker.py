"""TDD for the in-process job worker (claim + dispatch + drain)."""

import pytest
from sqlalchemy.orm import sessionmaker

from app.capture.djen import ComunicacaoDTO
from app.prazo_engine.factory import build_calendar
from app.queue.jobs import create_job
from app.queue.worker import WorkerClients, claim_next_job, dispatch, run_once
from app.sor import models


class FakeDjen:
    def __init__(self, items):
        self._items = items
        self.calls = []

    def consultar(self, oab, uf, **kw):
        self.calls.append((oab, uf, kw))
        return self._items


class FakeDatajud:
    def consultar_processo(self, numero_processo, *, tribunal):
        return None


@pytest.fixture
def calendar():
    return build_calendar([2024, 2025])


@pytest.fixture
def escritorio(db_session):
    esc = models.Escritorio(nome="Escritório Teste")
    db_session.add(esc)
    db_session.flush()
    return esc


@pytest.fixture
def session_factory(db_session):
    return sessionmaker(bind=db_session.bind, autoflush=False, expire_on_commit=False)


def _comunicacao(fonte_id="111"):
    return ComunicacaoDTO.from_item(
        {
            "id": fonte_id,
            "numero_processo": "0000001-00.2024.8.26.0100",
            "siglaTribunal": "TJSP",
            "tipoComunicacao": "Intimação",
            "texto": "Intimada para manifestar em 15 dias.",
            "data_disponibilizacao": "2024-09-06",
        }
    )


def _clients():
    return WorkerClients(djen=FakeDjen([]), datajud=FakeDatajud(), calendar=build_calendar([2024, 2025]))


def test_claim_next_job_picks_oldest_queued_and_marks_running(db_session, escritorio):
    j1 = create_job(
        db_session,
        tipo="captura_oab",
        entidade="escritorio",
        entidade_id=escritorio.id,
        payload={
            "oab": "1",
            "uf": "SP",
            "escritorio_id": escritorio.id,
            # Janela obrigatoria: sem ela o executor recusa a captura.
            "data_inicio": "2024-09-01",
            "data_fim": "2024-09-30",
        },
    )
    j2 = create_job(
        db_session,
        tipo="captura_oab",
        entidade="escritorio",
        entidade_id=escritorio.id,
        payload={"oab": "2", "uf": "SP", "escritorio_id": escritorio.id},
    )
    db_session.commit()

    claimed = claim_next_job(db_session)
    assert claimed.id == j1.id
    assert claimed.status == "running"
    # o segundo continua queued
    j2_fresh = db_session.get(models.JobExecucao, j2.id)
    assert j2_fresh.status == "queued"


def test_claim_next_job_returns_none_when_empty(db_session):
    assert claim_next_job(db_session) is None


def test_dispatch_captura_oab_executes_and_marks_completed(db_session, escritorio, calendar):
    job = create_job(
        db_session,
        tipo="captura_oab",
        entidade="escritorio",
        entidade_id=escritorio.id,
        payload={
            "oab": "12345",
            "uf": "SP",
            "escritorio_id": escritorio.id,
            "data_inicio": "2024-09-01",
            "data_fim": "2024-09-30",
            "dias_default": 15,
        },
    )
    db_session.commit()

    djen = FakeDjen([_comunicacao()])
    clients = WorkerClients(djen=djen, datajud=FakeDatajud(), calendar=calendar)
    dispatch(db_session, db_session.get(models.JobExecucao, job.id), clients, batch_days=15)

    assert djen.calls  # consultou DJEN
    job_fresh = db_session.get(models.JobExecucao, job.id)
    assert job_fresh.status == "completed"
    assert job_fresh.resultado["intimacoes_novas"] == 1


def test_run_once_drains_all_queued_jobs(session_factory, db_session, escritorio, calendar):
    for i in range(3):
        create_job(
            db_session,
            tipo="captura_oab",
            entidade="escritorio",
            entidade_id=escritorio.id,
            payload={
                "oab": str(i),
                "uf": "SP",
                "escritorio_id": escritorio.id,
                "data_inicio": "2024-09-01",
                "data_fim": "2024-09-10",
            },
        )
    db_session.commit()  # torna os jobs visíveis às sessões próprias de run_once
    processed = run_once(
        session_factory,
        clients=_clients(),
        batch_days=15,
        commit_each=lambda s: s.commit(),
    )

    assert processed == 3
    sess = session_factory()
    try:
        statuses = [j.status for j in sess.query(models.JobExecucao).order_by(models.JobExecucao.id)]
        assert statuses == ["completed", "completed", "completed"]
        assert sess.query(models.Intimacao).count() == 0  # FakeDjen retorna []
    finally:
        sess.close()


def test_run_once_continues_after_job_failure(session_factory, db_session, escritorio, calendar):
    # Cria e COMMITA os jobs na conexão compartilhada antes de drenar: run_once
    # abre sessões próprias, então jobs só flushed (não commitados) podem ficar
    # invisíveis conforme o estado da conexão — daí commitar aqui.
    good = create_job(
        db_session,
        tipo="captura_oab",
        entidade="escritorio",
        entidade_id=escritorio.id,
        payload={
            "oab": "1",
            "uf": "SP",
            "escritorio_id": escritorio.id,
            # Janela obrigatoria: sem ela o executor recusa a captura.
            "data_inicio": "2024-09-01",
            "data_fim": "2024-09-30",
        },
    )
    bad = create_job(
        db_session,
        tipo="captura_oab",
        entidade="escritorio",
        entidade_id=escritorio.id,
        payload={"foo": "bar"},
    )
    db_session.commit()

    processed = run_once(
        session_factory,
        clients=_clients(),
        commit_each=lambda s: s.commit(),
    )

    assert processed == 2
    sess = session_factory()
    try:
        good_fresh = sess.get(models.JobExecucao, good.id)
        bad_fresh = sess.get(models.JobExecucao, bad.id)
        assert good_fresh.status == "completed"
        assert bad_fresh.status == "failed"
        assert "payload de captura incompleto" in (bad_fresh.erro or "")
    finally:
        sess.close()
