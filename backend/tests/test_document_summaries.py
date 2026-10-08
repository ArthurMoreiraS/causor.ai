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
    load_summary_input,
    generate_summary,
    persist_summary,
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
    capture = open_capture(db_session, processo_instancia=instance, usuario_id=1, fonte="upload")
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


@pytest.mark.parametrize("profile,task", [("padrao", "context"), ("aprofundada", "draft")])
def test_summary_profile_routes_to_task_model_and_keeps_citation_checks(
    db_session, document_with_chunks, monkeypatch, profile, task,
):
    from app.settings import settings
    version, chunks = document_with_chunks
    digest = DocumentDigest(resumo="Resumo", fatos=[], pedidos=[], decisoes=[], prazos=[],
                            incertezas=[], citations=[ChunkCitation(chunk_id=chunks[0].id, quote=chunks[0].texto[:60])])
    calls = []
    def provider(**kw):
        calls.append(kw)
        return _FakeProvider(digest)
    monkeypatch.setattr("app.autos.summarizer.get_provider", provider)
    snapshot = load_summary_input(db_session, version)
    result = generate_summary(snapshot, profile=profile)
    assert result.digest is not None
    assert calls == [{"model": getattr(settings, f"claude_{'context' if task == 'context' else 'draft'}_model"), "task": task}]
    summary = persist_summary(db_session, snapshot, result)
    assert summary.dados["processamento"]["perfil"] == profile
    digest.citations[0].quote = "Citação ausente no original"
    assert generate_summary(snapshot, profile=profile).digest is None


def test_summary_checkpoint_rejects_changed_source(db_session, document_with_chunks):
    version, chunks = document_with_chunks
    snapshot = load_summary_input(db_session, version)
    digest = DocumentDigest(resumo="Resumo", fatos=[], pedidos=[], decisoes=[], prazos=[],
                            incertezas=[], citations=[ChunkCitation(chunk_id=chunks[0].id, quote=chunks[0].texto[:60])])
    result = generate_summary(snapshot, provider=_FakeProvider(digest))
    assert result.digest is not None
    chunks[0].texto = "Texto alterado enquanto o provedor trabalhava."
    db_session.flush()
    with pytest.raises(InvalidCitationError, match="summary_input_changed"):
        persist_summary(db_session, snapshot, result)
    assert db_session.query(models.DocumentoResumo).count() == 0


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
    assert "nenhuma citação confere" in resumo.error


def test_literal_span_aceita_omissao_de_aposto_e_devolve_o_trecho_original():
    from app.autos.summarizer import literal_span

    fonte = ("A denegação de mandado de segurança por inadequação da via eleita — especificamente pela "
             "ausência de prova pré-constituída — não faz coisa julgada material em relação a posterior ação.")
    citacao = "A denegação de mandado de segurança por inadequação da via eleita não faz coisa julgada material"
    span = literal_span(citacao, fonte)
    assert span is not None and span in fonte
    assert span.startswith("A denegação") and span.endswith("material")


def test_literal_span_normaliza_simbolos_e_recusa_parafrase():
    from app.autos.summarizer import literal_span

    fonte = "violariam o art. 169 da Lei nº 8.112/1990 e a Instrução Normativa nº 076/2013"
    assert literal_span("art. 169 da Lei n° 8.112/1990", fonte) is not None
    assert literal_span("É lícita a prova consistente em gravação ambiental", "a gravação ambiental realizada por um dos interlocutores") is None
    assert literal_span("Lei 8.112 viola o art. 169 da norma", fonte) is None


def test_citacao_que_nao_confere_e_descartada_sem_derrubar_o_resumo(db_session, document_with_chunks):
    version, chunks = document_with_chunks
    good = chunks[0].texto.split()[:6]
    digest = DocumentDigest(
        resumo="Resumo com uma citação boa e uma inventada.", fatos=[], pedidos=[], decisoes=[], prazos=[],
        incertezas=[],
        citations=[ChunkCitation(chunk_id=chunks[0].id, quote=" ".join(good)),
                   ChunkCitation(chunk_id=chunks[0].id, quote="TRECHO QUE NAO EXISTE AQUI")],
    )
    resumo = summarize_document(db_session, version=version, provider=_FakeProvider(digest))
    assert resumo.status == "complete"
    assert [c["quote"] for c in resumo.citations] == [" ".join(good)]
    assert any("descartada" in item for item in resumo.dados["incertezas"])


def _pages(count):
    from app.autos.summarizer import SummaryChunk, SummaryInput

    chunks = tuple(SummaryChunk(id=i, pagina=i, texto=f"Página {i}: o autor pagou aluguel de R$ 2.300,00.")
                   for i in range(1, count + 1))
    return SummaryInput(1, "a" * 64, "complete", "Documento: Autos\n\n", chunks)


class _TruncatingProvider:
    """Corta a resposta sempre que recebe mais de uma página."""

    def __init__(self, error=None):
        self.calls = []
        self._error = error

    def complete_structured(self, *, system, user, schema, max_tokens):
        import re

        from app.agent.llm import LLMOutputInvalidError

        ids = [int(value) for value in re.findall(r"chunk_id=(\d+)", user)]
        self.calls.append((ids, max_tokens))
        if self._error is not None:
            raise self._error
        if len(ids) > 1:
            raise LLMOutputInvalidError("A resposta do modelo veio incompleta ou fora do formato esperado")
        return DocumentDigest(resumo=f"Parte {ids[0]}", fatos=[], pedidos=[], decisoes=[], prazos=[],
                              incertezas=[], citations=[ChunkCitation(chunk_id=ids[0], quote=f"Página {ids[0]}")])


def test_truncated_summary_is_split_until_each_part_fits():
    provider = _TruncatingProvider()

    result = generate_summary(_pages(4), provider=provider)

    assert result.error is None
    assert result.parts == 4
    assert [citation.chunk_id for citation in result.digest.citations] == [1, 2, 3, 4]
    assert result.digest.resumo == "Parte 1\n\nParte 2\n\nParte 3\n\nParte 4"
    assert provider.calls[0] == ([1, 2, 3, 4], 6000)


def test_single_page_that_does_not_fit_still_fails():
    from app.agent.llm import LLMOutputInvalidError

    always = _TruncatingProvider(error=LLMOutputInvalidError("cortada"))
    result = generate_summary(_pages(1), provider=always)

    assert result.digest is None
    assert result.error == "LLMOutputInvalidError"
    assert len(always.calls) == 1


def test_transport_failure_is_not_split():
    from app.agent.llm import LLMProviderError

    provider = _TruncatingProvider(error=LLMProviderError("falha HTTP no endpoint LLM"))
    result = generate_summary(_pages(4), provider=provider)

    assert result.digest is None
    assert result.error == "LLMProviderError"
    assert len(provider.calls) == 1
