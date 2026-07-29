"""Deterministic tribunal -> processing-system inference.

The processing system (PJe / e-SAJ / Projudi / EPROC) is a property of the
*tribunal*, which we already know from the DJEN ``siglaTribunal`` at capture
time. Deriving it here is instant and offline — no DataJud call — which is what
the software needs to route filing (and populate the "Sistema" filter). DataJud,
when it returns the field, is authoritative and overrides this guess.

Sem default silencioso: o registro em ``court_routing`` cobre explicitamente os
tribunais conhecidos — os quatro sistemas, os TJs estaduais, TRFs, os 24 TRTs,
TST/TSE e os 27 TREs. Sigla fora do registro devolve ``"DESCONHECIDO"``, não um
palpite: chutar "PJe" mandava calado um tribunal de e-SAJ/eproc para o fluxo
errado (o TRF2, por exemplo, é eproc e o default o classificava como PJe).

``verificado`` distingue entrada conferida contra o portal oficial de entrada
declarada mas com URL a confirmar. Sistemas migram; corrija a entrada quando um
tribunal for conhecidamente outro. Palpite errado é barrado pelo gate de
aprovação humana antes de qualquer protocolo, nunca agido em silêncio.
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
