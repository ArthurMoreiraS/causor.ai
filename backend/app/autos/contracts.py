"""Manifestos recebidos do agente local (enumeração dos autos).

Pydantic com ``extra="forbid"``: o agente só envia campos conhecidos; nada de
payload arbitrário entrando no backend.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict


class ManifestDocumentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    external_id: str
    nome: str
    tipo: str | None
    ordem: int
    parent_external_id: str | None
    data_documento: date | None
    sigiloso: bool
    mime_type: str | None
    size_hint: int | None
    download_ref: str


class ManifestInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cursor_complete: bool
    documents: list[ManifestDocumentInput]
    evidence: dict
