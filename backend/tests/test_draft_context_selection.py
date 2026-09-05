"""Bounded drafting keeps the inventory and summaries, and traces exact sources."""

from dataclasses import replace

import pytest

from app.autos.context import ContextBundle
from app.agent.context_selection import DraftContextBudgetError, select_draft_context


def _citation(doc, chunk, quote):
    return {"documento_id": doc, "documento_arquivo_id": doc + 100,
            "chunk_id": chunk, "pagina": 2, "quote": quote}


def _bundle(citations):
    return ContextBundle(
        contexto_id=7, source_fingerprint="snapshot",
        inventory_text="Inventário: DOC-1 e DOC-2",
        consolidated_text="Resumo DOC-1: deferido. Resumo DOC-2: impugnado.",
        cited_excerpts="", citations=tuple(citations),
    )


def test_selection_preserves_inventory_summaries_and_exact_citations():
    bundle = _bundle([_citation(1, 11, "Decisão deferida."), _citation(2, 21, "Pedido impugnado.")])
    result = select_draft_context(bundle, query="decisão", timeline="Histórico", max_bytes=5000)
    assert bundle.inventory_text in result.text
    assert bundle.consolidated_text in result.text
    assert "Histórico" in result.text
    assert result.citations == bundle.citations
    assert result.metadata["excerpts_omitted"] == 0
    assert result.metadata["input_bytes"] == len(result.text.encode("utf-8"))


def test_selection_prioritizes_relevance_but_keeps_opposing_document():
    citations = [_citation(1, 11, "Taxas de expediente. " * 18),
                 _citation(1, 12, "Prescrição acolhida. " * 18),
                 _citation(2, 21, "Prescrição impugnada. " * 18)]
    bundle = _bundle(citations)
    result = select_draft_context(bundle, query="prescricao", max_bytes=1500)
    assert {c["chunk_id"] for c in result.citations} == {12, 21}
    assert result.metadata["excerpts_omitted"] == 1
    assert result.warnings
    assert len(result.text.encode("utf-8")) <= 1500
    assert result == select_draft_context(bundle, query="prescricao", max_bytes=1500)


def test_mandatory_summaries_are_never_silently_truncated():
    bundle = replace(_bundle([]), consolidated_text="Decisão importante. " * 1000)
    with pytest.raises(DraftContextBudgetError):
        select_draft_context(bundle, query="", max_bytes=1500)


def test_at_least_one_complete_excerpt_per_represented_document_must_fit():
    bundle = _bundle([_citation(1, 11, "é" * 2000), _citation(2, 21, "Outro documento.")])
    with pytest.raises(DraftContextBudgetError):
        select_draft_context(bundle, query="Outro", max_bytes=1500)


def test_duplicate_quotes_do_not_consume_budget_twice():
    quote = _citation(1, 11, "Trecho preservado.")
    result = select_draft_context(_bundle([quote, quote]), query="", max_bytes=1500)
    assert len(result.citations) == 1
    assert result.text.count('"Trecho preservado."') == 1


def test_supplemental_history_is_omitted_as_whole_lines_with_warning():
    result = select_draft_context(_bundle([]), query="", timeline="x" * 20000, max_bytes=1500)
    assert "x" * 100 not in result.text
    assert result.metadata["timeline_omitted"]
    assert result.warnings


def test_drafter_rejects_oversize_prompt_before_initializing_provider(monkeypatch):
    from app.agent import drafter
    from app.agent.classifier import ClassificacaoIntimacao
    from app.settings import settings

    monkeypatch.setattr(settings, "draft_prompt_max_bytes", 5000)
    monkeypatch.setattr(drafter, "get_provider", lambda **kw: pytest.fail("provider initialized"))
    with pytest.raises(DraftContextBudgetError):
        drafter.draft_peticao(
            intimacao_texto="é" * 4000, contexto_processo={},
            classificacao=ClassificacaoIntimacao(tipo="Ciência", peticao_sugerida="Manifestação",
                prazo_dias=None, dias_uteis=True, resumo="Ciência", confianca=0.5),
        )


def test_api_reports_budget_failure_without_saving_draft(client, db_session, seeded, monkeypatch):
    from app.settings import settings
    from app.sor import models
    from tests.conftest import seed_ready_context

    seed_ready_context(db_session, seeded)
    notice = models.Intimacao(processo_id=seeded.id, escritorio_id=seeded.escritorio_id,
                             fonte="DJEN", fonte_id="oversized", teor="é" * 4000)
    db_session.add(notice)
    db_session.commit()
    monkeypatch.setattr(settings, "draft_prompt_max_bytes", 5000)
    monkeypatch.setattr("app.agent.service.classify_intimacao", lambda *a: pytest.fail("LLM called"))
    response = client.post(f"/intimacoes/{notice.id}/draft")
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "draft_context_budget_exceeded"
    assert db_session.query(models.Peticao).count() == 0
