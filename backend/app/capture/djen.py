"""DJEN / Comunica client — captures court communications (intimações).

Capture uses the official API only (never scraping). Endpoint:
``GET /api/v1/comunicacao`` on ``comunicaapi.pje.jus.br``, polled by OAB/court.

The item schema on the live API mixes snake_case and camelCase and evolves;
this DTO maps the fields we rely on and keeps the full ``raw`` payload so the
normalization layer can adapt without a client change. Confirm exact query
params/field names against the live Swagger before production use.
"""

from __future__ import annotations

from datetime import date

import httpx
from pydantic import BaseModel, Field, field_validator

from app.settings import settings


class ComunicacaoDTO(BaseModel):
    id: str
    numero_processo: str | None = None
    tribunal: str | None = Field(default=None, alias="siglaTribunal")
    tipo_comunicacao: str | None = Field(default=None, alias="tipoComunicacao")
    orgao: str | None = Field(default=None, alias="nomeOrgao")
    texto: str | None = None
    data_disponibilizacao: date | None = None
    link: str | None = None
    raw: dict = Field(default_factory=dict)

    model_config = {"populate_by_name": True}

    @field_validator("id", mode="before")
    @classmethod
    def _coerce_id(cls, v: object) -> str:
        return str(v)

    @classmethod
    def from_item(cls, item: dict) -> "ComunicacaoDTO":
        dto = cls.model_validate(item)
        dto.raw = item
        return dto


class DjenClient:
    def __init__(self, http: httpx.Client | None = None) -> None:
        self._http = http or httpx.Client(
            base_url=settings.djen_base_url, timeout=settings.http_timeout_seconds
        )

    def consultar(
        self,
        oab: str,
        uf: str,
        *,
        data_inicio: date | None = None,
        data_fim: date | None = None,
        pagina: int = 1,
        itens_por_pagina: int = 100,
    ) -> list[ComunicacaoDTO]:
        params: dict[str, str | int] = {
            "numeroOab": oab,
            "ufOab": uf,
            "pagina": pagina,
            "itensPorPagina": itens_por_pagina,
        }
        if data_inicio:
            params["dataDisponibilizacaoInicio"] = data_inicio.isoformat()
        if data_fim:
            params["dataDisponibilizacaoFim"] = data_fim.isoformat()

        response = self._http.get("/comunicacao", params=params)
        response.raise_for_status()
        body = response.json()
        items = body.get("items") or []
        return [ComunicacaoDTO.from_item(item) for item in items]
