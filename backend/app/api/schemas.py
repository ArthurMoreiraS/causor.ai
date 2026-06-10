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
    teor: str | None
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


class RevisarPrazoRequest(BaseModel):
    usuario_id: int = 1
    descricao: str | None = None
    data_inicio: date | None = None
    dias: int | None = None
    dias_uteis: bool | None = None
    data_fatal: date | None = None


class MarcarPrazoCumpridoRequest(BaseModel):
    usuario_id: int = 1


class CaptureOabRequest(BaseModel):
    oab: str
    uf: str
    escritorio_id: int | None = None
    dias_default: int = 15
    data_inicio: date | None = None
    data_fim: date | None = None


class CaptureDemoRequest(BaseModel):
    escritorio_id: int | None = None
    dias_default: int = 15


class CaptureResultOut(BaseModel):
    intimacoes_novas: int
    processos_enriquecidos: int
    prazos_registrados: int


class ReviewQueueItem(BaseModel):
    intimacao: IntimacaoOut
    processo: ProcessoOut | None
    prazo: PrazoOut | None
    peticao: PeticaoOut | None
    status: str
    risco: str
    dias_para_vencer: int | None


class DashboardMetric(BaseModel):
    key: str
    label: str
    value: int


class WorkflowStep(BaseModel):
    key: str
    label: str
    detail: str
    status: str


class ConnectorStatus(BaseModel):
    key: str
    name: str
    detail: str
    status: str


class AuditSignal(BaseModel):
    key: str
    title: str
    detail: str


class OperationalDashboard(BaseModel):
    metrics: list[DashboardMetric]
    workflow: list[WorkflowStep]
    connectors: list[ConnectorStatus]
    audit_signals: list[AuditSignal]
