from hashlib import sha256
from pathlib import Path

import pytest

from app.autos.contracts import ManifestDocumentInput, ManifestInput
from app.autos.service import (
    confirm_document_upload,
    open_capture,
    record_initial_manifest,
)
from app.autos.worker import DocumentProcessingError, run_document_processing_job
from app.sor import models
from app.storage.objects import LocalObjectStore

FIXTURES = Path(__file__).parent / "fixtures" / "pdfs"


@pytest.fixture
def instance(db_session, seeded):
    row = models.ProcessoInstancia(
        processo_id=seeded.id,
        escritorio_id=seeded.escritorio_id,
        sistema="PJe",
        tribunal="TJMG",
        grau="1",
        url_base="https://example.invalid/pje",
        status="active",
    )
    db_session.add(row)
    db_session.flush()
    return row


@pytest.fixture
def object_store(tmp_path):
    return LocalObjectStore(tmp_path)


def _manifest(ids=("a",)):
    return ManifestInput(
        cursor_complete=True,
        documents=[
            ManifestDocumentInput(
                external_id=value,
                nome=f"{value}.pdf",
                tipo=None,
                ordem=index,
                parent_external_id=None,
                data_documento=None,
                sigiloso=False,
                mime_type="application/pdf",
                size_hint=None,
                download_ref=f"opaque:{value}",
            )
            for index, value in enumerate(ids, start=1)
        ],
        evidence={},
    )


def _confirmed_version(db_session, instance, object_store, data):
    capture = open_capture(db_session, processo_instancia=instance, usuario_id=1)
    record_initial_manifest(db_session, capture=capture, manifest=_manifest())
    object_store.put_bytes("test/a.pdf", data, "application/pdf")
    return confirm_document_upload(
        db_session,
        capture=capture,
        external_id="a",
        object_key="test/a.pdf",
        reported_sha256=sha256(data).hexdigest(),
        object_store=object_store,
    )


def test_confirm_enqueues_processing_job_and_worker_extracts(
    db_session, seeded, instance, object_store
):
    data = (FIXTURES / "textual.pdf").read_bytes()
    version = _confirmed_version(db_session, instance, object_store, data)

    job = (
        db_session.query(models.JobExecucao)
        .filter_by(tipo="process_document", entidade_id=version.id)
        .one()
    )
    assert job.status == "queued"

    processed = run_document_processing_job(
        db_session, documento_arquivo_id=version.id, object_store=object_store
    )
    assert processed.extraction_status == "complete"
    assert processed.page_count == 2
    assert processed.text_sha256

    chunks = (
        db_session.query(models.DocumentoTrecho)
        .filter_by(documento_arquivo_id=version.id)
        .all()
    )
    assert {chunk.pagina for chunk in chunks} == {1, 2}


def test_worker_is_idempotent_for_completed_versions(
    db_session, seeded, instance, object_store
):
    data = (FIXTURES / "textual.pdf").read_bytes()
    version = _confirmed_version(db_session, instance, object_store, data)
    run_document_processing_job(
        db_session, documento_arquivo_id=version.id, object_store=object_store
    )
    again = run_document_processing_job(
        db_session, documento_arquivo_id=version.id, object_store=object_store
    )
    assert again.extraction_status == "complete"


def test_worker_marks_unextractable_pdf_as_failed(
    db_session, seeded, instance, object_store, monkeypatch
):
    from app.autos.extraction import PdfExtractionError

    # PDF com header/EOF válidos mas corpo corrompido: passa na validação de
    # magic bytes do upload e falha na extração.
    data = b"%PDF-1.4\ncorpo corrompido sem estrutura\n%%EOF\n"
    version = _confirmed_version(db_session, instance, object_store, data)

    def _raise(_):
        raise PdfExtractionError("page 1 has no extractable text")

    monkeypatch.setattr("app.autos.worker.extract_pdf_pages", _raise)
    with pytest.raises(DocumentProcessingError) as exc:
        run_document_processing_job(
            db_session, documento_arquivo_id=version.id, object_store=object_store
        )
    assert exc.value.code == "extraction_failed"
    db_session.refresh(version)
    assert version.extraction_status == "failed"
