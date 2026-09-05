"""Deterministic selection over cited summaries from one verified context.

The inventory and ALL summaries are mandatory. Excerpts are ranked lexically,
with one per represented document before filling remaining space. Never cut a
quote or a summary to make a prompt fit. Budgets are UTF-8 bytes, not tokens;
the operator must size them for the configured model's context window.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import re
import unicodedata

from app.autos.context import ContextBundle


class DraftContextBudgetError(ValueError):
    code = "draft_context_budget_exceeded"

    def __init__(self):
        super().__init__(
            "O conteúdo necessário para esta minuta excede a capacidade configurada. "
            "Os autos foram preservados. A geração precisa de ajuste de capacidade "
            "pelo responsável pelo Causor."
        )


def ensure_budget(text: str, max_bytes: int) -> None:
    if len(text.encode("utf-8")) > max_bytes:
        raise DraftContextBudgetError()


@dataclass(frozen=True)
class DraftContextSelection:
    text: str
    citations: tuple[dict, ...]
    metadata: dict
    warnings: tuple[str, ...]


_STOP_WORDS = frozenset(
    "para pelo pela pelos pelas como sobre entre esta este estes estas uma uns umas "
    "que com dos das nao nos nas aos ao seu sua seus suas foi ser por das do da de "
    "processo intimacao parte peticao manifestacao".split()
)


def _terms(text: str) -> set[str]:
    normalized = unicodedata.normalize("NFKD", text.casefold())
    normalized = "".join(c for c in normalized if not unicodedata.combining(c))
    return {word for word in re.findall(r"\w+", normalized)
            if len(word) > 2 and word not in _STOP_WORDS}


def _excerpt(citation: dict) -> str:
    return f"[DOC-{citation['documento_id']} p.{citation.get('pagina')}] \"{citation.get('quote')}\""


def select_draft_context(
    bundle: ContextBundle, *, query: str, timeline: str | None = None, max_bytes: int
) -> DraftContextSelection:
    citations = list({
        (c["documento_id"], c["documento_arquivo_id"], c["chunk_id"], c.get("quote")): c
        for c in bundle.citations
    }.values())
    query_terms = _terms(query)
    ranked = sorted(range(len(citations)), key=lambda i: (
        -len(query_terms & _terms(citations[i].get("quote") or "")), i,
    ))
    representatives: dict[int, int] = {}
    for index in ranked:
        representatives.setdefault(citations[index]["documento_id"], index)
    selected = set(representatives.values())
    excerpts = [_excerpt(c) for c in citations]
    scope = (
        "[ESCOPO DA REDAÇÃO]\nInventário e resumos preservados integralmente. "
        "Excertos selecionados por correspondência de termos, com representação "
        "de cada documento citado. A seleção não prova suficiência jurídica; "
        "confira as fontes e os argumentos contrários.\n\nExcertos citáveis dos autos:"
    )
    mandatory = "\n\n".join((bundle.consolidated_text, bundle.inventory_text, scope))
    used_bytes = len(mandatory.encode("utf-8"))
    costs = [1 + len(excerpt.encode("utf-8")) for excerpt in excerpts]
    used_bytes += sum(costs[i] for i in selected)
    if used_bytes > max_bytes:
        raise DraftContextBudgetError()
    for index in ranked:
        if index not in selected and used_bytes + costs[index] <= max_bytes:
            selected.add(index)
            used_bytes += costs[index]
    text = mandatory + "".join("\n" + excerpts[i] for i in sorted(selected))

    # Supplementary SOR chronology never displaces a case-file summary/source.
    timeline_lines: list[str] = []
    timeline_omitted = False
    timeline_budget = min(12000, max_bytes - used_bytes)
    for line in (timeline or "").splitlines():
        cost = len(line.encode("utf-8")) + 1
        if cost + 2 <= timeline_budget:
            timeline_lines.append(line)
            timeline_budget -= cost
        else:
            timeline_omitted = True
            break  # keep the most recent prefix; never skip to older events
    if timeline_lines:
        text += "\n\n" + "\n".join(timeline_lines)
    ensure_budget(text, max_bytes)
    omitted = len(citations) - len(selected)
    warnings: list[str] = []
    if omitted:
        warnings.append(
            f"Seleção de fontes: {len(selected)} de {len(citations)} excertos enviados "
            "ao redator. Inventário e resumos foram mantidos; confira também as "
            "demais fontes dos autos ao revisar a minuta."
        )
    if timeline_omitted:
        warnings.append("Histórico suplementar limitado para esta redação; os resumos dos autos foram preservados.")
    return DraftContextSelection(
        text=text, citations=tuple(citations[i] for i in sorted(selected)),
        warnings=tuple(warnings), metadata={
            "method": "lexical_document_coverage_v1",
            "contexto_id": bundle.contexto_id,
            "source_fingerprint": bundle.source_fingerprint,
            "max_bytes": max_bytes, "input_bytes": len(text.encode("utf-8")),
            "input_sha256": sha256(text.encode("utf-8")).hexdigest(),
            "excerpts_total": len(citations), "excerpts_selected": len(selected),
            "excerpts_omitted": omitted, "timeline_omitted": timeline_omitted,
            "chunk_ids": [citations[i]["chunk_id"] for i in sorted(selected)],
        },
    )
