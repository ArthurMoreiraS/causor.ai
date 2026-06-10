"""DataJud client — captures process metadata and movements (andamentos).

Official CNJ public API. Endpoint per court:
``POST /api_publica_<tribunal>/_search`` with an Elasticsearch-style JSON body
and header ``Authorization: APIKey <public CNJ key>``. The public key is
published on the DataJud Wiki and may be rotated by CNJ — it is supplied via
config at runtime, never hardcoded permanently.
"""

from __future__ import annotations

from datetime import date, datetime

import httpx
from pydantic import BaseModel, Field, field_validator

from app.settings import settings


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    # DataJud uses ISO timestamps like "2024-01-15T00:00:00.000Z".
    return datetime.fromisoformat(value.replace("Z", "+00:00")).date()


def _name_of(value: object) -> str | None:
    """DataJud nests {codigo, nome}; accept either a dict or a plain string."""
    if isinstance(value, dict):
        return value.get("nome")
    if isinstance(value, str):
        return value
    return None


class MovimentoDTO(BaseModel):
    codigo: int | None = None
    nome: str | None = None
    data_hora: datetime | None = Field(default=None, alias="dataHora")

    model_config = {"populate_by_name": True}


class ProcessoDTO(BaseModel):
    numero_processo: str = Field(alias="numeroProcesso")
    classe: str | None = None
    tribunal: str | None = None
    data_ajuizamento: date | None = Field(default=None, alias="dataAjuizamento")
    orgao_julgador: str | None = Field(default=None, alias="orgaoJulgador")
    sistema: str | None = None
    movimentos: list[MovimentoDTO] = Field(default_factory=list)
    raw: dict = Field(default_factory=dict)

    model_config = {"populate_by_name": True}

    @field_validator("classe", "sistema", "orgao_julgador", mode="before")
    @classmethod
    def _flatten_named(cls, v: object) -> str | None:
        return _name_of(v)

    @field_validator("data_ajuizamento", mode="before")
    @classmethod
    def _parse_ajuizamento(cls, v: object) -> date | None:
        return _parse_date(v) if isinstance(v, str) else v

    @classmethod
    def from_source(cls, source: dict) -> "ProcessoDTO":
        dto = cls.model_validate(source)
        dto.raw = source
        return dto


class DatajudClient:
    def __init__(self, api_key: str | None = None, http: httpx.Client | None = None) -> None:
        self._api_key = api_key or settings.datajud_api_key
        self._http = http or httpx.Client(
            base_url=settings.datajud_base_url, timeout=settings.http_timeout_seconds
        )

    def consultar_processo(self, numero_processo: str, *, tribunal: str) -> ProcessoDTO | None:
        endpoint = f"/api_publica_{tribunal.lower()}/_search"
        body = {"query": {"match": {"numeroProcesso": numero_processo}}}
        headers = {"Authorization": f"APIKey {self._api_key}"}

        response = self._http.post(endpoint, json=body, headers=headers)
        response.raise_for_status()
        hits = response.json().get("hits", {}).get("hits", [])
        if not hits:
            return None
        return ProcessoDTO.from_source(hits[0]["_source"])
