"""Pydantic schemas for the Causor API."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class IntimacaoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    processo_id: int | None
    fonte: str
    numero_processo: str | None
    tribunal: str | None
    tipo_comunicacao: str | None
    data_disponibilizacao: date | None
    data_publicacao: date | None


class PrazoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    processo_id: int | None
    intimacao_id: int | None
    descricao: str | None
    data_inicio: date
    dias: int
    dias_uteis: bool
    data_fatal: date
    cumprido: bool


class ProcessoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    numero: str
    classe: str | None
    tribunal: str | None
    orgao_julgador: str | None
    sistema: str | None


class PeticaoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    processo_id: int
    prazo_id: int | None
    tipo: str | None
    conteudo: str | None
    status: str
    aprovada_por: int | None
    protocolada_em: datetime | None


class DraftRequest(BaseModel):
    calendar_years: list[int] | None = None


class DraftResponse(BaseModel):
    prazo: PrazoOut
    peticao: PeticaoOut
    classificacao: dict


class ApprovePeticaoRequest(BaseModel):
    usuario_id: int
