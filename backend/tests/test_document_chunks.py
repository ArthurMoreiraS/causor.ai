from hashlib import sha256
from pathlib import Path

import pytest

from app.autos.chunks import chunk_pages, persist_chunks, search_process_chunks
from app.autos.contracts import ManifestDocumentInput, ManifestInput
from app.autos.extraction import ExtractedPage
from app.autos.service import (
    confirm_document_upload,
    open_capture,
    record_initial_manifest,
)
from app.autos.worker import run_document_processing_job
from app.sor import models
from app.storage.objects import LocalObjectStore

FIXTURES = Path(__file__).parent / "fixtures" / "pdfs"


def test_chunks_never_cross_page_boundaries():
    pages = (
        ExtractedPage(page=1, text="A" * 4500, ocr=False),
        ExtractedPage(page=2, text="B" * 100, ocr=True),
    )
    chunks = chunk_pages(pages, max_chars=4000, overlap=400)
    assert [c.page for c in chunks] == [1, 1, 2]
    assert chunks[0].text[-400:] == chunks[1].text[:400]
    assert chunks[2].ocr is True


def test_chunk_indices_are_sequential_per_page():
    pages = (ExtractedPage(page=1, text="X" * 9000, ocr=False),)
    chunks = chunk_pages(pages, max_chars=4000, overlap=400)
    assert [c.indice for c in chunks] == [0, 1, 2]
    assert all(c.page == 1 for c in chunks)


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
                tipo="Contrato",
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


def test_persist_is_idempotent_and_search_finds_text(
    db_session, seeded, instance, object_store
):
    data = (FIXTURES / "textual.pdf").read_bytes()
    capture = open_capture(db_session, processo_instancia=instance, usuario_id=1)
    record_initial_manifest(db_session, capture=capture, manifest=_manifest())
    object_store.put_bytes("test/a.pdf", data, "application/pdf")
    version = confirm_document_upload(
        db_session,
        capture=capture,
        external_id="a",
        object_key="test/a.pdf",
        reported_sha256=sha256(data).hexdigest(),
        object_store=object_store,
    )
    run_document_processing_job(
        db_session, documento_arquivo_id=version.id, object_store=object_store
    )
    # Reinserção é idempotente: mesmo conjunto de páginas, sem duplicar trechos.
    pages = (
        ExtractedPage(page=1, text="CONTRATO DE PRESTACAO DE SERVICOS", ocr=False),
        ExtractedPage(page=2, text="Disposicoes finais.", ocr=False),
    )
    persist_chunks(db_session, version=version, pages=pages)
    persist_chunks(db_session, version=version, pages=pages)
    rows = (
        db_session.query(models.DocumentoTrecho)
        .filter_by(documento_arquivo_id=version.id)
        .all()
    )
    assert len(rows) == 2

    results = search_process_chunks(
        db_session,
        escritorio_id=seeded.escritorio_id,
        processo_id=seeded.id,
        query="contrato",
    )
    assert results
    assert results[0]["pagina"] == 1
    assert "CONTRATO" in results[0]["texto"]


def test_search_is_tenant_scoped(db_session, seeded, instance, object_store):
    results = search_process_chunks(
        db_session,
        escritorio_id=seeded.escritorio_id + 999,
        processo_id=seeded.id,
        query="contrato",
    )
    assert results == []
