"""Recover original sources from the exact inventory used for this draft.

Summaries guide navigation but never restrict which original pages can be found.
All persisted references include version, page, text and content hashes.
"""
from dataclasses import replace
from hashlib import sha256

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.agent.context_selection import _terms, select_draft_context
from app.autos.context import ContextBundle
from app.sor import models


def original_sources(session: Session, *, processo: models.Processo, bundle: ContextBundle,
                     query: str, pinned: tuple[int, ...] = (), limit: int = 80) -> list[dict]:
    context = session.get(models.ContextoProcesso, bundle.contexto_id)
    if context is None or context.escritorio_id != processo.escritorio_id or context.processo_id != processo.id:
        raise ValueError("Contexto não pertence ao processo")
    version_ids = [item["documento_arquivo_id"] for item in context.inventario or []]
    chunk, version, document = models.DocumentoTrecho, models.DocumentoArquivo, models.Documento
    base = select(chunk, version, document).join(version, chunk.documento_arquivo_id == version.id).join(
        document, version.documento_id == document.id).where(
        version.id.in_(version_ids), document.processo_id == processo.id,
        document.escritorio_id == processo.escritorio_id)
    pinned_rows = session.execute(base.where(chunk.id.in_(pinned))).all() if pinned else []
    if {row[0].id for row in pinned_rows} != set(pinned):
        raise ValueError("Uma fonte fixada não pertence à versão atual deste trabalho")
    terms = sorted(_terms(query))[:80]
    if session.bind.dialect.name == "postgresql" and terms:
        phrase = " OR ".join(terms)
        tsquery = "websearch_to_tsquery('portuguese', :evidence_query)"
        stmt = base.where(text(f"to_tsvector('portuguese', documento_trecho.texto) @@ {tsquery}"))
        stmt = stmt.order_by(text(f"ts_rank_cd(to_tsvector('portuguese', documento_trecho.texto), {tsquery}) DESC"), chunk.id)
        rows = session.execute(stmt.limit(limit).params(evidence_query=phrase)).all()
    else:
        # Hermetic SQLite path; stream all pages so late documents cannot disappear behind a list cap.
        from heapq import nlargest
        scored = ((len(set(terms) & _terms(row[0].texto)), -row[0].id, row)
                  for row in session.execute(base).yield_per(200))
        rows = [row for score, _, row in nlargest(limit, scored, key=lambda item: (item[0], item[1])) if score]
    rows = [*pinned_rows, *rows]
    # Adjacent page supplies context around the hit; it is never considered a new legal fact automatically.
    neighbours = []
    for hit, _, _ in rows[:12]:
        neighbours.extend(session.execute(base.where(chunk.documento_arquivo_id == hit.documento_arquivo_id,
            chunk.pagina.in_([hit.pagina - 1, hit.pagina + 1])).order_by(chunk.pagina, chunk.indice).limit(6)).all())
    unique = {row[0].id: row for row in [*rows, *neighbours]}
    return [{"documento_id": d.id, "documento_arquivo_id": v.id, "chunk_id": c.id,
             "pagina": c.pagina, "indice": c.indice, "quote": c.texto,
             "sha256": v.sha256, "texto_sha256": c.texto_sha256, "nome": d.nome,
             "origem": "texto_original", "fixada": c.id in pinned, "ocr": c.ocr}
            for c, v, d in unique.values()]


def select_evidence(session: Session, *, processo: models.Processo, bundle: ContextBundle,
                    query: str, max_bytes: int, pinned: tuple[int, ...] = (), timeline: str | None = None):
    sources = original_sources(session, processo=processo, bundle=bundle, query=query, pinned=pinned)
    expanded = replace(bundle, citations=tuple([*bundle.citations, *sources]))
    selected = select_draft_context(expanded, query=query, max_bytes=max_bytes, timeline=timeline,
                                    pinned_chunk_ids=pinned)
    metadata = {**selected.metadata, "method": "original_text_and_summary_v2",
                "original_sources_recovered": len(sources), "pinned_chunk_ids": list(pinned)}
    # Store enough evidence to audit the exact text even if OCR is recomputed later.
    citations = []
    for citation in selected.citations:
        version = session.get(models.DocumentoArquivo, citation["documento_arquivo_id"])
        citations.append({**citation, "sha256": version.sha256 if version else citation.get("sha256"),
            "texto_sha256": citation.get("texto_sha256") or sha256(citation["quote"].encode()).hexdigest()})
    return replace(selected, metadata=metadata, citations=tuple(citations))
