"""Interface única de driver de protocolo + dispatch por sistema.

Um driver por sistema (PJe/e-SAJ/EPROC/Projudi) atrás da mesma interface. Na
demo, ``mode="sandbox"`` manda todos os sistemas para o ``SandboxDriver``
determinístico. No modo real o backend **nunca** devolve driver de navegador:
a execução acontece no agente local (``jobs._dispatch_real_filing_to_agent``
enfileira ``prepare_filing`` antes de chegar aqui) — o antigo adapter
in-process exigia ``storage_state``, cuja única fonte (cofre de sessão) foi
removida do backend.
"""

from __future__ import annotations

from app.connectors.contracts import FilingDriver
from app.connectors.sandbox_driver import SandboxDriver

__all__ = [
    "FilingDriver",
    "UnsupportedFilingSystemError",
    "get_filing_driver",
]


class UnsupportedFilingSystemError(RuntimeError):
    """Sistema sem conector no modo pedido (real roda só no agente local)."""


def get_filing_driver(sistema: str, *, mode: str) -> FilingDriver:
    """Resolve ``(sistema, mode)`` no driver de protocolo apropriado."""
    if mode == "sandbox":
        return SandboxDriver(sistema)
    raise UnsupportedFilingSystemError(
        f"protocolo real de {sistema} roda no agente local, nao no backend; "
        "use o modo sandbox ou registre o protocolo manualmente"
    )
