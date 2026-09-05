"""Processamento persistente de documentos fora do request HTTP.

O upload confirma e enfileira; este worker baixa do storage para arquivo
temporário (hash em blocos de 1 MiB), respeita o teto de tamanho, extrai
texto/OCR por página. OCR/LLM rodam fora de transações; checkpoints curtos
exigem posse vigente do job. Interrupções preservam a extração concluída.
"""

from __future__ import annotations

from hashlib import sha256
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import time
from uuid import uuid4

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.autos.extraction import PdfExtractionError, extract_pdf_pages
from app.autos.leases import Heartbeat, LeaseLost, check_expiry, database_now, guard_lease
from app.settings import settings
from app.sor import models
from app.storage.objects import ObjectStore, get_object_store


class DocumentProcessingError(RuntimeError):
    def __init__(self, code: str, detail: str | None = None):
        super().__init__(detail or code)
        self.code = code


def _hash_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def run_document_processing_job(
    session: Session,
    *,
    documento_arquivo_id: int,
    object_store: ObjectStore | None = None,
) -> models.DocumentoArquivo:
    """Extrai texto/OCR de uma versão verificada e persiste o resultado."""
    version = session.get(models.DocumentoArquivo, documento_arquivo_id)
    if version is None:
        raise DocumentProcessingError("not_found", f"documento_arquivo {documento_arquivo_id}")
    if version.extraction_status in {"complete", "unsupported_mime"}:
        return version
    try:
        result = extract_document(version, object_store=object_store)
    except DocumentProcessingError as exc:
        version.extraction_status = "failed"
        version.extraction_error = str(exc)[:2000]
        session.flush()
        raise
    persist_extraction(session, version, result)
    return version


def extract_document(version: models.DocumentoArquivo, *, object_store=None):
    """Only uses detached scalar metadata. No database session during IO/OCR."""
    if version.size_bytes > settings.document_max_bytes:
        raise DocumentProcessingError("document_too_large")

    store = object_store or get_object_store()
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix="causor-autos-", suffix=".pdf", delete=False
        ) as tmp:
            tmp_path = Path(tmp.name)
        store.download_to(version.storage_key, tmp_path)

        if tmp_path.stat().st_size > settings.document_max_bytes:
            raise DocumentProcessingError("document_too_large")
        if _hash_file(tmp_path) != version.sha256:
            raise DocumentProcessingError("hash_mismatch")

        try:
            return extract_pdf_pages(tmp_path.read_bytes())
        except PdfExtractionError as exc:
            raise DocumentProcessingError("extraction_failed", str(exc)) from exc
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)


def persist_extraction(session: Session, version: models.DocumentoArquivo, result) -> None:
    version.page_count = result.page_count
    version.text_sha256 = result.text_sha256
    version.extraction_status = "complete"
    version.extraction_error = None
    _persist_pages(session, version, result)
    session.flush()


def _persist_pages(session: Session, version: models.DocumentoArquivo, result) -> None:
    """Persiste trechos citáveis limitados à página de origem."""
    from app.autos import chunks as chunks_module

    chunks_module.persist_chunks(session, version=version, pages=result.pages)


def enqueue_process_purge(
    session: Session, *, processo: models.Processo, actor: str
) -> models.JobExecucao:
    """Descarte é explícito e assíncrono: nunca apaga milhares de objetos
    dentro de um request. Não existe expiração automática por idade."""
    from app.queue.jobs import create_job

    return create_job(
        session,
        tipo="purge_process_objects",
        entidade="processo",
        entidade_id=processo.id,
        payload={"processo_id": processo.id},
        ator=actor,
    )


def run_purge_process_objects_job(
    session: Session,
    *,
    processo_id: int,
    object_store: ObjectStore | None = None,
    batch_size: int = 100,
) -> dict:
    """Apaga do storage os objetos de um processo, em lotes, com auditoria.

    Lista as chaves pelo banco (fonte da verdade), apaga em lotes limitados e
    registra contagens/hashes no audit log antes de qualquer remoção de
    metadados (que segue a ordem de limpeza de tenant existente).
    """
    store = object_store or get_object_store()
    versions = list(
        session.scalars(
            select(models.DocumentoArquivo)
            .join(models.Documento, models.Documento.id == models.DocumentoArquivo.documento_id)
            .where(models.Documento.processo_id == processo_id)
        )
    )
    deleted = 0
    hashes: list[str] = []
    for start in range(0, len(versions), batch_size):
        for version in versions[start : start + batch_size]:
            store.delete(version.storage_key)
            hashes.append(version.sha256)
            deleted += 1

    processo = session.get(models.Processo, processo_id)
    session.add(
        models.AuditLog(
            escritorio_id=processo.escritorio_id if processo else None,
            ator="system",
            acao="process_objects_purged",
            entidade="processo",
            entidade_id=processo_id,
            detalhe={"deleted": deleted, "sha256": hashes},
        )
    )
    session.flush()
    return {"deleted": deleted}


def claim_due_purge_jobs(session: Session, *, limit: int = 10) -> list[models.JobExecucao]:
    stmt = (
        select(models.JobExecucao)
        .where(
            models.JobExecucao.tipo == "purge_process_objects",
            models.JobExecucao.status == "queued",
        )
        .order_by(models.JobExecucao.id)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    jobs = list(session.scalars(stmt))
    for job in jobs:
        job.status = "running"
    session.flush()
    return jobs


def process_due_purges(session_factory) -> int:
    """Drena jobs `purge_process_objects`. Retorna a contagem processada."""
    processed = 0
    while True:
        with session_factory() as session:
            jobs = claim_due_purge_jobs(session, limit=1)
            if not jobs:
                return processed
            job = jobs[0]
            processo_id = (job.payload or {}).get("processo_id")
            try:
                result = run_purge_process_objects_job(session, processo_id=processo_id)
                job.status = "completed"
                job.resultado = result
            except Exception as exc:  # noqa: BLE001 - falha vira estado observável
                job.status = "failed"
                job.erro = str(exc)[:500]
            session.commit()
        processed += 1


def claim_due_mni_captures(session: Session, *, limit: int = 10) -> list[models.JobExecucao]:
    stmt = (
        select(models.JobExecucao)
        .where(
            models.JobExecucao.tipo == "mni_capture",
            models.JobExecucao.status == "queued",
        )
        .order_by(models.JobExecucao.id)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    jobs = list(session.scalars(stmt))
    for job in jobs:
        job.status = "running"
    session.flush()
    return jobs


def process_due_mni_captures(session_factory) -> int:
    """Drena jobs `mni_capture`. Retorna a contagem processada."""
    from app.connectors.mni.executor import run_mni_capture_job

    processed = 0
    while True:
        with session_factory() as session:
            jobs = claim_due_mni_captures(session, limit=1)
            if not jobs:
                return processed
            job = jobs[0]
            capture_id = (job.payload or {}).get("capture_id")
            try:
                capture = run_mni_capture_job(session, capture_id=capture_id)
                job.status = "completed"
                job.resultado = {"capture_id": capture_id, "status": capture.status}
            except Exception as exc:  # noqa: BLE001 - falha vira estado observável
                job.status = "failed"
                job.erro = str(getattr(exc, "code", exc))[:500]
            session.commit()
        processed += 1


def claim_due_processing_jobs(session: Session, *, limit: int = 10) -> list[models.JobExecucao]:
    stmt = (
        select(models.JobExecucao)
        .where(
            models.JobExecucao.tipo == "process_document",
            models.JobExecucao.status == "queued",
        )
        .order_by(models.JobExecucao.id)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    jobs = list(session.scalars(stmt))
    for job in jobs:
        job.status = "running"
        job.lease_token = str(uuid4())
        job.lease_expires_at = database_now(session) + timedelta(seconds=settings.document_lease_seconds)
    session.flush()
    return jobs


def recover_stale_document_jobs(
    session: Session, *, older_than_minutes: int, now: datetime | None = None, limit: int = 100,
) -> list[models.JobExecucao]:
    """Recover expired leases or old legacy jobs, excluding locked checkpoints."""
    if older_than_minutes <= 0 or limit <= 0:
        raise ValueError("recovery age and batch size must be positive")
    now = now or database_now(session)
    cutoff = now - timedelta(minutes=older_than_minutes)
    jobs = list(session.scalars(select(models.JobExecucao).where(
        models.JobExecucao.tipo == "process_document", models.JobExecucao.status == "running",
        or_(models.JobExecucao.lease_expires_at <= now,
            and_(models.JobExecucao.lease_expires_at.is_(None), models.JobExecucao.updated_at <= cutoff)),
    ).order_by(models.JobExecucao.id).limit(limit).with_for_update(skip_locked=True)))
    for job in jobs:
        payload = job.payload or {}
        version_id = payload.get("documento_arquivo_id")
        version = session.get(models.DocumentoArquivo, version_id) if isinstance(version_id, int) else None
        document = session.get(models.Documento, version.documento_id) if version else None
        session.add(models.AuditLog(
            escritorio_id=document.escritorio_id if document else payload.get("escritorio_id"),
            ator="system", acao="document_job_recovered", entidade="job_execucao", entidade_id=job.id,
            detalhe={"previous_status": "running", "previous_updated_at": job.updated_at.isoformat()},
        ))
        job.status = "queued"
        job.erro = None
        job.lease_token = None
        job.lease_expires_at = None
    session.flush()
    return jobs


def _process_document_stages(session_factory, job_id: int, token: str, version_id: int, heartbeat) -> None:
    from app.autos.summarizer import generate_summary, load_summary_input, persist_summary

    with session_factory() as session:
        guard_lease(session, job_id, token)
        version = session.get(models.DocumentoArquivo, version_id)
        if version is None:
            raise DocumentProcessingError("not_found")
        session.expunge(version)
    if version.extraction_status not in {"complete", "unsupported_mime"}:
        try:
            result = extract_document(version)
        except DocumentProcessingError as exc:
            heartbeat.check()
            with session_factory() as session:
                job = guard_lease(session, job_id, token)
                current = session.scalar(select(models.DocumentoArquivo).where(
                    models.DocumentoArquivo.id == version_id,
                ).with_for_update())
                if current and current.extraction_status != "complete":
                    current.extraction_status = "failed"
                    current.extraction_error = str(exc)[:2000]
                check_expiry(session, job)
                session.commit()
            raise
        heartbeat.check()
        with session_factory() as session:
            job = guard_lease(session, job_id, token)
            current = session.scalar(select(models.DocumentoArquivo).where(
                models.DocumentoArquivo.id == version_id,
            ).with_for_update())
            if current is None or (current.sha256, current.storage_key) != (version.sha256, version.storage_key):
                raise DocumentProcessingError("document_input_changed")
            # A duplicate job may have completed it; preserve existing citation IDs.
            if current.extraction_status != "complete":
                persist_extraction(session, current, result)
            job.resultado = {"documento_arquivo_id": version_id, "stage": "extracted"}
            check_expiry(session, job)
            session.commit()

    with session_factory() as session:
        guard_lease(session, job_id, token)
        summary = session.scalar(select(models.DocumentoResumo).where(
            models.DocumentoResumo.documento_arquivo_id == version_id,
        ))
        if summary is not None and summary.status == "complete":
            return
        version = session.get(models.DocumentoArquivo, version_id)
        if version is None:
            raise DocumentProcessingError("not_found")
        snapshot = load_summary_input(session, version)
    result = generate_summary(snapshot)
    heartbeat.check()
    with session_factory() as session:
        job = guard_lease(session, job_id, token)
        # Lock the version before reading the existing summary, including duplicate jobs.
        session.scalar(select(models.DocumentoArquivo).where(
            models.DocumentoArquivo.id == version_id,
        ).with_for_update())
        summary = session.scalar(select(models.DocumentoResumo).where(
            models.DocumentoResumo.documento_arquivo_id == version_id,
        ))
        if summary is None or summary.status != "complete":
            summary = persist_summary(session, snapshot, result)
        completed = summary.status == "complete"
        job.resultado = {"documento_arquivo_id": version_id, "stage": "summarized" if completed else "summary_failed"}
        check_expiry(session, job)
        session.commit()
    if not completed:
        raise DocumentProcessingError("summary_failed")


def _finish_document_job(session_factory, job_id: int, token: str, version_id: int, error: str | None):
    from app.autos.context import build_process_context

    with session_factory() as session:
        job = guard_lease(session, job_id, token)
        version = session.get(models.DocumentoArquivo, version_id)
        if version:
            document = session.get(models.Documento, version.documento_id)
            process = session.get(models.Processo, document.processo_id) if document else None
            if process:
                build_process_context(session, processo=process)
        # Context construction can wait on another publisher; check expiry again.
        check_expiry(session, job)
        job.status = "failed" if error else "completed"
        job.erro = error
        if not error:
            job.resultado = {"documento_arquivo_id": version_id}
        job.lease_token = None
        job.lease_expires_at = None
        session.commit()


def process_due_documents(
    session_factory,
    *,
    max_attempts: int | None = None,
    backoff_seconds: float = 1.0,
) -> int:
    """Drain documents with renewable leases and durable extraction/summary checkpoints."""
    attempts_ceiling = max_attempts or settings.document_processing_attempts
    with session_factory() as recovery_session:
        recover_stale_document_jobs(
            recovery_session, older_than_minutes=settings.document_recovery_after_minutes,
        )
        recovery_session.commit()
    processed = 0
    while True:
        with session_factory() as session:
            jobs = claim_due_processing_jobs(session, limit=1)
            if not jobs:
                return processed
            job = jobs[0]
            documento_arquivo_id = (job.payload or {}).get("documento_arquivo_id")
            job_id, token = job.id, job.lease_token
            session.commit()
        try:
            with Heartbeat(session_factory, job_id, token) as heartbeat:
                error = None
                for attempt in range(1, attempts_ceiling + 1):
                    heartbeat.check()
                    try:
                        _process_document_stages(session_factory, job_id, token, documento_arquivo_id, heartbeat)
                        error = None
                        break
                    except LeaseLost:
                        raise
                    except DocumentProcessingError as exc:
                        error = exc.code
                        break
                    except Exception as exc:  # noqa: BLE001 - bounded transient retries
                        error = type(exc).__name__
                        if attempt < attempts_ceiling:
                            time.sleep(backoff_seconds * (2 ** (attempt - 1)))
                heartbeat.check()
                _finish_document_job(session_factory, job_id, token, documento_arquivo_id, error)
        except LeaseLost:
            import logging

            logging.getLogger(__name__).warning("document_result_discarded job_id=%s", job_id)
        processed += 1


def run_autos_loop(session_factory, *, idle_seconds: float = 2.0) -> None:
    """Consumidor contínuo dos jobs de autos, separado da captura OAB."""
    import logging

    while True:
        try:
            processed = process_due_mni_captures(session_factory)
            processed += process_due_documents(session_factory)
            processed += process_due_purges(session_factory)
        except Exception:
            logging.getLogger(__name__).exception("autos_worker_cycle_failed")
            processed = 0
        if not processed:
            time.sleep(idle_seconds)


if __name__ == "__main__":
    from app.sor.db import SessionLocal

    run_autos_loop(SessionLocal)
