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

# Softplan e-SAJ.
_ESAJ = {"TJSP", "TJMS", "TJAL", "TJAC"}
# EPROC (TRF4 e tribunais que adotaram o sistema gaúcho/catarinense).
_EPROC = {"TJRS", "TJSC", "TJTO", "TRF4"}
# Projudi.
_PROJUDI = {"TJPR"}


def sistema_para_tribunal(tribunal: str | None) -> str | None:
    """Deduz o sistema processual a partir da sigla do tribunal (ex.: ``TJSP``).

    Retorna ``None`` quando não há tribunal para inferir. Caso contrário devolve
    um dos rótulos canônicos: ``"PJe"`` (default), ``"e-SAJ"``, ``"EPROC"`` ou
    ``"Projudi"``.
    """
    if not tribunal or not tribunal.strip():
        return None
    sigla = tribunal.strip().upper()
    if sigla in _ESAJ:
        return "e-SAJ"
    if sigla in _EPROC:
        return "EPROC"
    if sigla in _PROJUDI:
        return "Projudi"
    return "PJe"
