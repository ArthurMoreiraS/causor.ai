"""Perfis versionados de conector por (sistema, tribunal, grau, versão).

Um perfil descreve uma variante concreta de portal que foi (ou será)
homologada. Perfil novo nasce ``experimental``; só validação live recente
promove a ``supported`` (ver ``connectors/live_validation`` e a matriz de
cobertura).
"""

from __future__ import annotations

from dataclasses import dataclass

VALID_STATUSES = {"experimental", "supported", "degraded", "blocked"}


@dataclass(frozen=True)
class ConnectorCapabilities:
    read_autos: bool
    read_secret: bool
    prepare_filing: bool
    submit_filing: bool
    download_receipt: bool


@dataclass(frozen=True)
class ConnectorProfile:
    key: str
    sistema: str
    tribunal: str
    grau: str
    url_base: str
    filing_url: str | None
    version_marker: str
    status: str
    capabilities: ConnectorCapabilities
    receipt_protocol_pattern: str | None = None

    def __post_init__(self):
        if self.grau not in {"1", "2"}:
            raise ValueError("grau must be 1 or 2")
        if self.status not in VALID_STATUSES:
            raise ValueError("invalid connector profile status")
