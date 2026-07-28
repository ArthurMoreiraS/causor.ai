from hashlib import sha256
from pathlib import Path

import pytest

from app.autos.context import build_process_context, get_ready_context
from app.autos.contracts import ManifestDocumentInput, ManifestInput
from app.autos.service import (
    confirm_document_upload,
    finalize_capture,
    mark_not_applicable,
    open_capture,
    record_initial_manifest,
)
from app.autos.summarizer import summarize_document
from app.autos.worker import run_document_processing_job
from app.sor import models
from app.storage.objects import LocalObjectStore

FIXTURES = Path(__file__).parent / "fixtures" / "pdfs"


class _DigestProvider:
    """Provider fake: cita literalmente o primeiro chunk do documento."""

    def __init__(self, db_session):
        self._session = db_session

    def complete_structured(self, *, system, user, schema, max_tokens=2000):
        import re

        from app.autos.summarizer import ChunkCitation, DocumentDigest

        chunk_id = int(re.search(r"chunk_id=(\d+)", user).group(1))
        chunk = self._session.get(models.DocumentoTrecho, chunk_id)
        return DocumentDigest(
            resumo="Documento resumido para teste.",
            fatos=["Fato citado."],
            pedidos=[],
            decisoes=[],
            prazos=[],
            incertezas=[],
            citations=[ChunkCitation(chunk_id=chunk_id, quote=chunk.texto[:60])],
        )


def _manifest(ids):
    return ManifestInput(
        cursor_complete=True,
        documents=[
            ManifestDocumentInput(
                external_id=value,
                nome=f"Documento {value}.pdf",
                tipo="Decisão",
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


@pytest.fixture
def complete_extracted_process(db_session, seeded, tmp_path):
    """Processo com 1º grau completo (3 docs extraídos+resumidos) e 2º grau
    not_applicable com evidência."""
    store = LocalObjectStore(tmp_path)
    first = models.ProcessoInstancia(
        processo_id=seeded.id,
        escritorio_id=seeded.escritorio_id,
        sistema="PJe",
        tribunal="TJSP",
        grau="1",
        status="active",
    )
    second = models.ProcessoInstancia(
        processo_id=seeded.id,
        escritorio_id=seeded.escritorio_id,
        sistema="PJe",
        tribunal="TJSP",
        grau="2",
        status="active",
    )
    db_session.add_all([first, second])
    db_session.flush()

    manifest = _manifest(("a", "b", "c"))
    capture = open_capture(db_session, processo_instancia=first, usuario_id=1)
    record_initial_manifest(db_session, capture=capture, manifest=manifest)
    pdf = (FIXTURES / "textual.pdf").read_bytes()
    for item in capture.items:
        data = pdf + b"\n%" + item.external_id.encode() + b"\n%%EOF\n"
        key = f"test/{item.external_id}.pdf"
        store.put_bytes(key, data, "application/pdf")
        version = confirm_document_upload(
            db_session,
            capture=capture,
            external_id=item.external_id,
            object_key=key,
            reported_sha256=sha256(data).hexdigest(),
            object_store=store,
        )
        run_document_processing_job(
            db_session, documento_arquivo_id=version.id, object_store=store
        )
        summarize_document(db_session, version=version, provider=_DigestProvider(db_session))
    finalize_capture(db_session, capture=capture, final_manifest=manifest)
    assert capture.status == "complete"

    # 2º grau: conector provou não-aplicabilidade (com evidência).
    # Pelo caminho real de produção, não por linha escrita à mão — foi
    # exatamente essa fixture que escondeu o fato de que nada em produção
    # sabia selar `not_applicable`.
    na = open_capture(db_session, processo_instancia=second, usuario_id=1)
    mark_not_applicable(
        db_session,
        capture=na,
        evidence={"motivo": "processo sem recurso; sem autos de 2º grau"},
    )
    assert na.status == "not_applicable"
    return seeded


def test_context_inventory_contains_every_verified_current_document(
    db_session, complete_extracted_process
):
    context = build_process_context(db_session, processo=complete_extracted_process)
    assert context.status == "ready"
    assert context.cobertura["documents_total"] == 3
    assert context.cobertura["documents_summarized"] == 3
    assert len(context.inventario) == 3
    assert all(item["documento_arquivo_id"] for item in context.inventario)
    assert context.citations


def test_context_is_not_ready_without_second_degree_evidence(db_session, seeded):
    instancia = models.ProcessoInstancia(
        processo_id=seeded.id,
        escritorio_id=seeded.escritorio_id,
        sistema="PJe",
        tribunal="TJSP",
        grau="1",
        status="active",
    )
    db_session.add(instancia)
    db_session.flush()
    context = build_process_context(db_session, processo=seeded)
    assert context.status == "building"
    assert "instancia:2" in context.cobertura["missing"]


def test_ready_bundle_has_inventory_and_citation_labels(
    db_session, complete_extracted_process
):
    build_process_context(db_session, processo=complete_extracted_process)
    bundle = get_ready_context(db_session, processo=complete_extracted_process)
    assert bundle is not None
    assert "Inventário integral" in bundle.inventory_text
    assert "[DOC-" in bundle.cited_excerpts
    assert bundle.source_fingerprint


def test_bundle_is_rejected_when_fingerprint_is_stale(
    db_session, complete_extracted_process, tmp_path
):
    build_process_context(db_session, processo=complete_extracted_process)
    # Nova captura completa muda o estado atual → fingerprint antigo fica stale.
    store = LocalObjectStore(tmp_path / "v2")
    instancia = (
        db_session.query(models.ProcessoInstancia)
        .filter_by(processo_id=complete_extracted_process.id, grau="1")
        .one()
    )
    manifest = _manifest(("a", "b", "c", "d"))
    capture = open_capture(db_session, processo_instancia=instancia, usuario_id=1)
    record_initial_manifest(db_session, capture=capture, manifest=manifest)
    pdf = (FIXTURES / "textual.pdf").read_bytes()
    for item in capture.items:
        data = pdf + b"\n%v2-" + item.external_id.encode() + b"\n%%EOF\n"
        key = f"test/v2/{item.external_id}.pdf"
        store.put_bytes(key, data, "application/pdf")
        confirm_document_upload(
            db_session,
            capture=capture,
            external_id=item.external_id,
            object_key=key,
            reported_sha256=sha256(data).hexdigest(),
            object_store=store,
        )
    finalize_capture(db_session, capture=capture, final_manifest=manifest)
    assert capture.status == "complete"

    assert get_ready_context(db_session, processo=complete_extracted_process) is None


def test_draft_uses_context_bundle_and_never_leaks_vault(
    db_session, complete_extracted_process, monkeypatch
):
    from app.agent import service as agent_service
    from app.agent.classifier import ClassificacaoIntimacao
    from app.agent.drafter import MinutaGerada
    from app.prazo_engine.factory import build_calendar

    build_process_context(db_session, processo=complete_extracted_process)

    captured_prompt = {}

    def _fake_draft(**kwargs):
        captured_prompt.update(kwargs)
        return MinutaGerada(
            contexto_consolidado="ctx",
            analise_providencia="analise",
            minuta="minuta",
            alertas=[],
            confianca=0.9,
        )

    monkeypatch.setattr(agent_service, "draft_peticao", _fake_draft)
    monkeypatch.setattr(
        agent_service,
        "classify_intimacao",
        lambda teor: ClassificacaoIntimacao(
            tipo="Intimação para contestar",
            prazo_dias=15,
            dias_uteis=True,
            peticao_sugerida="Contestação",
            resumo="resumo",
            confianca=0.9,
        ),
    )

    intimacao = (
        db_session.query(models.Intimacao)
        .filter_by(processo_id=complete_extracted_process.id)
        .first()
    )
    calendar = build_calendar([2024, 2025, 2026])
    _prazo, peticao, _cls = agent_service.draft_from_intimacao(
        db_session, intimacao, calendar=calendar
    )

    historico = captured_prompt["historico"]
    assert "Inventário integral" in historico
    assert "[DOC-" in historico
    # Todos os resumos entram no input do redator.
    assert historico.count("Documento resumido para teste.") == 3
    # Nada de vault/sessão no prompt.
    assert "storage_state" not in str(captured_prompt).lower()
    assert "token" not in historico.lower()

    assert peticao.dossie["contexto_id"]
    assert peticao.dossie["source_fingerprint"]
    assert len(peticao.dossie["inventario"]) == 3
