"""Interface única de driver de protocolo + dispatch por sistema.

Um driver por sistema (PJe/e-SAJ/EPROC/Projudi) atrás da mesma interface. Trocar
o driver não mexe em job, vault, UI ou roteamento. Na demo, ``mode="sandbox"``
manda todos os sistemas para o ``SandboxDriver`` determinístico; no piloto real,
``mode="real"`` usa o conector real (PJe existe; os demais são incrementais).
"""

from __future__ import annotations

from typing import Protocol

from app.connectors.pje.connector import (
    PjeAssistedConnector,
    PjeFilingCheckpoint,
    PjeFilingPackage,
)
from app.connectors.sandbox_driver import SandboxDriver


class UnsupportedFilingSystemError(RuntimeError):
    """Sistema sem conector real (fora do modo sandbox)."""


class FilingDriver(Protocol):
    sistema: str

    def prepare_filing(
        self, package: PjeFilingPackage, *, submit: bool
    ) -> PjeFilingCheckpoint: ...


class PjeDriver:
    """Adapta o conector PJe existente à interface FilingDriver."""

    sistema = "PJe"

    def __init__(self) -> None:
        self._connector = PjeAssistedConnector()

    def prepare_filing(
        self, package: PjeFilingPackage, *, submit: bool = False
    ) -> PjeFilingCheckpoint:
        return self._connector.prepare_filing(package, submit=submit)


def get_filing_driver(sistema: str, *, mode: str) -> FilingDriver:
    """Resolve ``(sistema, mode)`` no driver de protocolo apropriado."""
    if mode == "sandbox":
        return SandboxDriver(sistema)
    if sistema == "PJe":
        return PjeDriver()
    raise UnsupportedFilingSystemError(
        f"sem conector real para {sistema}; use o modo sandbox ou registre o "
        "protocolo manualmente"
    )
