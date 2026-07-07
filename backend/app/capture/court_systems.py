"""Deterministic tribunal -> processing-system inference.

The processing system (PJe / e-SAJ / Projudi / EPROC) is a property of the
*tribunal*, which we already know from the DJEN ``siglaTribunal`` at capture
time. Deriving it here is instant and offline — no DataJud call — which is what
the software needs to route filing (and populate the "Sistema" filter). DataJud,
when it returns the field, is authoritative and overrides this guess.

Best-effort by design: the map covers the well-known non-PJe courts and defaults
everything else to PJe (the majority — Justiça Federal, do Trabalho, Eleitoral e
a maior parte dos TJs estaduais). Court systems migrate over time; correct an
entry here when a tribunal is known to be wrong. A wrong guess is caught by the
human approval gate before any filing, never acted on silently.
"""

from __future__ import annotations

from app.capture.court_routing import resolve_route


def sistema_para_tribunal(tribunal: str | None) -> str | None:
    """Deduz o sistema processual a partir da sigla do tribunal (ex.: ``TJSP``).

    Retorna ``None`` quando não há tribunal para inferir. Caso contrário devolve
    um dos rótulos canônicos: ``"PJe"`` (default), ``"e-SAJ"``, ``"EPROC"`` ou
    ``"Projudi"``. A fonte da verdade é o registro em ``court_routing``.
    """
    route = resolve_route(tribunal)
    return route.sistema if route is not None else None
