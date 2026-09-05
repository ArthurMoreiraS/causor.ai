from hashlib import sha256
from pathlib import Path

import pytest

from app.autos.contracts import ManifestDocumentInput, ManifestInput
from app.autos.service import (
    confirm_document_upload,
    open_capture,
    record_initial_manifest,
)
from app.autos.summarizer import (
    ChunkCitation,
    DocumentDigest,
    InvalidCitationError,
    summarize_document,
    validate_citations,
)
from app.autos.worker import run_document_processing_job
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


@pytest.fixture
def document_with_chunks(db_session, seeded, instance, object_store):
    manifest = ManifestInput(
        cursor_complete=True,
        documents=[
            ManifestDocumentInput(
                external_id="a",
                nome="Contrato.pdf",
                tipo="Contrato",
                ordem=1,
                parent_external_id=None,
                data_documento=None,
                sigiloso=False,
                mime_type="application/pdf",
                size_hint=None,
                download_ref="opaque:a",
            )
        ],
        evidence={},
    )
    capture = open_capture(db_session, processo_instancia=instance, usuario_id=1)
    record_initial_manifest(db_session, capture=capture, manifest=manifest)
    data = (FIXTURES / "textual.pdf").read_bytes()
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
    chunks = (
        db_session.query(models.DocumentoTrecho)
        .filter_by(documento_arquivo_id=version.id)
        .order_by(models.DocumentoTrecho.pagina)
        .all()
    )
    return version, chunks


def test_summary_rejects_quote_not_present_in_chunk(db_session, document_with_chunks):
    _version, chunks = document_with_chunks
    digest = DocumentDigest(
        resumo="Resumo",
        fatos=[],
        pedidos=[],
        decisoes=[],
        prazos=[],
        incertezas=[],
        citations=[ChunkCitation(chunk_id=chunks[0].id, quote="FRASE INVENTADA")],
    )
    with pytest.raises(InvalidCitationError):
        validate_citations(db_session, digest)


def test_quote_matching_ignores_accents_and_whitespace(db_session, document_with_chunks):
    _version, chunks = document_with_chunks
    digest = DocumentDigest(
        resumo="Resumo",
        fatos=[],
        pedidos=[],
        decisoes=[],
        prazos=[],
        incertezas=[],
        citations=[
            ChunkCitation(chunk_id=chunks[0].id, quote="CONTRATO DE PRESTACAO DE SERVICOS")
        ],
    )
    validate_citations(db_session, digest)


def test_summary_without_citations_is_rejected(db_session, document_with_chunks):
    digest = DocumentDigest(resumo="Afirmação sem fonte", fatos=[], pedidos=[], decisoes=[],
                            prazos=[], incertezas=[], citations=[])
    with pytest.raises(InvalidCitationError):
        validate_citations(db_session, digest)


def test_citation_from_another_document_version_is_rejected(
    db_session, document_with_chunks
):
    version, chunks = document_with_chunks
    digest = DocumentDigest(
        resumo="Resumo",
        fatos=[],
        pedidos=[],
        decisoes=[],
        prazos=[],
        incertezas=[],
        citations=[
            ChunkCitation(chunk_id=chunks[0].id, quote="CONTRATO DE PRESTACAO DE SERVICOS")
        ],
    )
    with pytest.raises(InvalidCitationError):
        validate_citations(db_session, digest, documento_arquivo_id=version.id + 999)


class _FakeProvider:
    def __init__(self, digest):
        self._digest = digest

    def complete_structured(self, *, system, user, schema, max_tokens=2000):
        assert "chunk_id" in user
        return self._digest

    def complete_text(self, *, system, user, max_tokens):  # pragma: no cover
        raise NotImplementedError


def test_summarize_document_accepts_valid_citations(db_session, document_with_chunks):
    version, chunks = document_with_chunks
    digest = DocumentDigest(
        resumo="Contrato de prestação de serviços entre as partes.",
        fatos=["Partes celebraram contrato."],
        pedidos=[],
        decisoes=[],
        prazos=[],
        incertezas=[],
        citations=[
            ChunkCitation(chunk_id=chunks[0].id, quote="CONTRATO DE PRESTACAO DE SERVICOS")
        ],
    )
    resumo = summarize_document(db_session, version=version, provider=_FakeProvider(digest))
    assert resumo.status == "complete"
    assert resumo.citations and resumo.citations[0]["chunk_id"] == chunks[0].id


def test_summarize_document_marks_invented_citation_as_failed(
    db_session, document_with_chunks
):
    version, chunks = document_with_chunks
    digest = DocumentDigest(
        resumo="Resumo com citação inventada.",
        fatos=[],
        pedidos=[],
        decisoes=[],
        prazos=[],
        incertezas=[],
        citations=[ChunkCitation(chunk_id=chunks[0].id, quote="TRECHO QUE NAO EXISTE AQUI")],
    )
    resumo = summarize_document(db_session, version=version, provider=_FakeProvider(digest))
    assert resumo.status == "failed"
    assert "quote nao encontrado" in resumo.error
