"""Processamento persistente de documentos fora do request HTTP.

O upload confirma e enfileira; este worker baixa do storage para arquivo
temporário (hash em blocos de 1 MiB), respeita o teto de tamanho, extrai
texto/OCR por página e nunca segura transação de banco durante OCR/LLM.
"""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import tempfile
import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.autos.extraction import PdfExtractionError, extract_pdf_pages
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
    if version.size_bytes > settings.document_max_bytes:
        version.extraction_status = "failed"
        version.extraction_error = "document_too_large"
        session.flush()
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
            version.extraction_status = "failed"
            version.extraction_error = "document_too_large"
            session.flush()
            raise DocumentProcessingError("document_too_large")
        if _hash_file(tmp_path) != version.sha256:
            version.extraction_status = "failed"
            version.extraction_error = "hash_mismatch_on_processing"
            session.flush()
            raise DocumentProcessingError("hash_mismatch")

        try:
            result = extract_pdf_pages(tmp_path.read_bytes())
        except PdfExtractionError as exc:
            version.extraction_status = "failed"
            version.extraction_error = str(exc)[:2000]
            session.flush()
            raise DocumentProcessingError("extraction_failed", str(exc)) from exc

        version.page_count = result.page_count
        version.text_sha256 = result.text_sha256
        version.extraction_status = "complete"
        version.extraction_error = None
        _persist_pages(session, version, result)
        session.flush()
        return version
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)


def _persist_pages(session: Session, version: models.DocumentoArquivo, result) -> None:
    """Persiste trechos citáveis. Implementação de chunking chega na Task 5;

    até lá cada página vira um trecho único (índice 0), já citável.
    """
    from app.autos import chunks as chunks_module

    chunks_module.persist_chunks(session, version=version, pages=result.pages)


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
    session.flush()
    return jobs


def process_due_documents(
    session_factory,
    *,
    max_attempts: int | None = None,
    backoff_seconds: float = 1.0,
) -> int:
    """Drena jobs `process_document`. Retorna a contagem processada."""
    attempts_ceiling = max_attempts or settings.document_processing_attempts
    processed = 0
    while True:
        with session_factory() as session:
            jobs = claim_due_processing_jobs(session, limit=1)
            if not jobs:
                return processed
            job = jobs[0]
            job_id = job.id
            documento_arquivo_id = (job.payload or {}).get("documento_arquivo_id")
            session.commit()

        for attempt in range(1, attempts_ceiling + 1):
            try:
                with session_factory() as session:
                    run_document_processing_job(
                        session, documento_arquivo_id=documento_arquivo_id
                    )
                    job = session.get(models.JobExecucao, job_id)
                    job.status = "completed"
                    job.resultado = {"documento_arquivo_id": documento_arquivo_id}
                    session.commit()
                break
            except DocumentProcessingError as exc:
                with session_factory() as session:
                    job = session.get(models.JobExecucao, job_id)
                    job.status = "failed"
                    job.erro = exc.code
                    session.commit()
                break
            except Exception as exc:  # noqa: BLE001 - transiente: retry com backoff
                if attempt >= attempts_ceiling:
                    with session_factory() as session:
                        job = session.get(models.JobExecucao, job_id)
                        job.status = "failed"
                        job.erro = str(exc)[:500]
                        session.commit()
                    break
                time.sleep(backoff_seconds * (2 ** (attempt - 1)))
        processed += 1
