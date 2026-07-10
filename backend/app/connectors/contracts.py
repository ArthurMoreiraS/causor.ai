"""Contratos neutros de sistema judicial para leitura e protocolo.

Tipos compartilhados por todos os drivers (PJe/e-SAJ/EPROC/Projudi). Este
módulo não pode importar nada sob ``connectors/pje`` — a neutralidade de
sistema é o contrato.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol


@dataclass(frozen=True)
class CourtTarget:
    processo_instancia_id: int
    processo_id: int
    numero_processo: str
    sistema: str
    tribunal: str
    grau: str
    url_base: str


@dataclass(frozen=True)
class CourtDocumentRef:
    external_id: str
    nome: str
    tipo: str | None
    ordem: int
    data_documento: date | None
    sigiloso: bool
    mime_type: str | None
    size_hint: int | None
    download_ref: str
    parent_external_id: str | None = None


@dataclass(frozen=True)
class CourtManifestSnapshot:
    target: CourtTarget
    documentos: tuple[CourtDocumentRef, ...]
    cursor_complete: bool
    source_fingerprint: str
    captured_at: datetime
    evidence: dict


@dataclass(frozen=True)
class FilingPackage:
    peticao_id: int
    processo_instancia_id: int
    numero_processo: str
    tribunal: str
    sistema: str
    grau: str
    tipo_peticao: str | None
    pdf_bytes: bytes


@dataclass(frozen=True)
class FilingCheckpoint:
    checkpoint: str
    modo: str
    irreversible: bool
    evidence: dict


class CourtReaderDriver(Protocol):
    sistema: str

    def enumerate_documents(self, target: CourtTarget) -> CourtManifestSnapshot: ...

    def download_document(self, target: CourtTarget, ref: CourtDocumentRef) -> bytes: ...


class FilingDriver(Protocol):
    sistema: str

    def prepare_filing(
        self, package: FilingPackage, *, submit: bool = False
    ) -> FilingCheckpoint: ...
