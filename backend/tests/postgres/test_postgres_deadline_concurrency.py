"""Disposable PostgreSQL schema verifies capture and enqueue row locking."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.capture.djen import ComunicacaoDTO
from app.capture.normalize import normalize_intimacao
from app.prazo_engine.pipeline import enqueue_analysis
from app.sor import models


def test_same_source_is_separate_per_tenant_and_one_job_per_notice(pg_engine):
    with Session(pg_engine) as session:
        first = models.Escritorio(nome="A")
        second = models.Escritorio(nome="B")
        session.add_all([first, second])
        session.commit()
        ids = (first.id, second.id)

    dto = ComunicacaoDTO.from_item({"id": "same-djen-id", "numero_processo": "0000001-00.2026.8.26.0100",
        "siglaTribunal": "TJSP", "tipoComunicacao": "Intimação",
        "texto": "Manifestar em 5 dias úteis.", "data_disponibilizacao": "2026-09-25"})
    barrier = Barrier(3)

    def capture(office_id):
        with Session(pg_engine, autoflush=False, expire_on_commit=False) as session:
            barrier.wait()
            notice = normalize_intimacao(session, dto, escritorio_id=office_id)
            session.flush()
            enqueue_analysis(session, notice)
            session.commit()
            return notice.id

    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(capture, office_id) for office_id in (ids[0], ids[0], ids[1])]
        notice_ids = [future.result() for future in futures]
    assert notice_ids[0] == notice_ids[1]
    assert notice_ids[2] != notice_ids[0]
    with Session(pg_engine) as session:
        notices = session.scalars(select(models.Intimacao)).all()
        jobs = session.scalars(select(models.JobExecucao).where(
            models.JobExecucao.tipo == "analise_prazo")).all()
        assert len(notices) == len(jobs) == 2
        assert {job.payload["escritorio_id"] for job in jobs} == set(ids)
