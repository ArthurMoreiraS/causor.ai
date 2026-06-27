"""DJEN / Comunica client — captures court communications (intimações).

Capture uses the official API only (never scraping). Endpoint:
``GET /api/v1/comunicacao`` on ``comunicaapi.pje.jus.br``, polled by OAB/court.

The item schema on the live API mixes snake_case and camelCase and evolves;
this DTO maps the fields we rely on and keeps the full ``raw`` payload so the
normalization layer can adapt without a client change. Confirm exact query
params/field names against the live Swagger before production use.
"""

from __future__ import annotations

import time
from collections.abc import Callable
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
    def __init__(
        self,
        http: httpx.Client | None = None,
        *,
        max_attempts: int = 3,
        backoff_seconds: float = 1.0,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self._http = http or httpx.Client(
            base_url=settings.djen_base_url,
            timeout=httpx.Timeout(
                settings.http_timeout_seconds,
                connect=10.0,
                read=settings.http_timeout_seconds,
            ),
        )
        self._max_attempts = max_attempts
        self._backoff_seconds = backoff_seconds
        self._sleeper = sleeper

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

        response = self._get_with_retry("/comunicacao", params=params)
        response.raise_for_status()
        body = response.json()
        items = body.get("items") or []
        return [ComunicacaoDTO.from_item(item) for item in items]

    def _get_with_retry(
        self, path: str, *, params: dict[str, str | int]
    ) -> httpx.Response:
        last_error: httpx.HTTPError | None = None
        for attempt in range(1, self._max_attempts + 1):
            try:
                return self._http.get(path, params=params)
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_error = exc
                if attempt >= self._max_attempts:
                    break
                self._sleeper(self._backoff_seconds * (2 ** (attempt - 1)))
        assert last_error is not None
        raise last_error
