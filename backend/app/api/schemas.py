"""Pydantic schemas for the Causor API."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


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


class ProximoPrazoOut(BaseModel):
    data_fatal: date
    cumprido: bool
    descricao: str | None


class ProcessoResumoOut(BaseModel):
    """Processo já cruzado no servidor para a lista da página de Processos:
    próximo prazo + contagens + campos de busca. Substitui o join client-side de
    4 listas paginadas, que subcontava (dashboard 200 vs página 195)."""

    id: int
    numero: str
    classe: str | None
    tribunal: str | None
    orgao_julgador: str | None
    sistema: str | None
    intimacoes_count: int
    peticoes_count: int
    proximo_prazo: ProximoPrazoOut | None
    intimacao_tipo: str | None
    peticao_tipo: str | None


class ProcessoResumoLista(BaseModel):
    total: int  # COUNT real do tenant; fonte de verdade do número do cabeçalho
    items: list[ProcessoResumoOut]


class PeticaoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    processo_id: int
    prazo_id: int | None
    tipo: str | None
    conteudo: str | None
    dossie: dict | None = None
    status: str
    aprovada_por: int | None
    protocolada_em: datetime | None


class DraftRequest(BaseModel):
    calendar_years: list[int] | None = None


class DraftResponse(BaseModel):
    prazo: PrazoOut
    peticao: PeticaoOut
    classificacao: dict


class EditPeticaoRequest(BaseModel):
    conteudo: str | None = None
    # aprovada/protocolada exigem os endpoints de gate; PATCH não atalha o gate.
    status: Literal["rascunho", "em_revisao"] | None = None


class RevisarPrazoRequest(BaseModel):
    descricao: str | None = None
    data_inicio: date | None = None
    dias: int | None = None
    dias_uteis: bool | None = None
    data_fatal: date | None = None


class CaptureOabRequest(BaseModel):
    oab: str
    uf: str
    dias_default: int = 15
    data_inicio: date | None = None
    data_fim: date | None = None


class CaptureResultOut(BaseModel):
    intimacoes_novas: int
    processos_enriquecidos: int
    prazos_registrados: int
    djen_indisponivel: bool = False
    djen_erro: str | None = None


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tipo: str
    status: str
    entidade: str | None
    entidade_id: int | None
    payload: dict | None
    resultado: dict | None
    erro: str | None
    created_at: datetime
    updated_at: datetime


class UsuarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    escritorio_id: int
    nome: str
    email: str | None = None
    oab: str | None = None
    oab_uf: str | None = None


class EscritorioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    cnpj: str | None = None


class MeOut(BaseModel):
    usuario_id: int
    escritorio_id: int
    email: str


class OperationalProfileOut(BaseModel):
    usuario: UsuarioOut
    escritorio: EscritorioOut


class OperationalProfileUpdate(BaseModel):
    nome_usuario: str | None = Field(default=None, min_length=2, max_length=255)
    nome_escritorio: str | None = Field(default=None, min_length=2, max_length=255)
    cnpj: str | None = Field(default=None, max_length=20)
    oab: str | None = Field(default=None, max_length=20)
    oab_uf: str | None = Field(default=None, max_length=2)


class ProtocolarAsyncRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    credencial_id: int | None = None


class ConfirmarProtocoloRequest(BaseModel):
    protocolo: str = Field(min_length=3, max_length=100)
    comprovante_uri: str | None = Field(default=None, max_length=1024)
    credencial_id: int | None = None


class CreateCredencialAssinaturaRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provedor: str = Field(min_length=2, max_length=50)
    referencia_externa: str = Field(min_length=4, max_length=255)


def _walk_keys(value):
    if isinstance(value, dict):
        for key, nested in value.items():
            yield key
            yield from _walk_keys(nested)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_keys(item)


class CreatePjeSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tribunal: str = Field(min_length=2, max_length=50)
    url_base: str = Field(min_length=10, max_length=255)
    storage_state: dict = Field(min_length=1)

    @field_validator("storage_state")
    @classmethod
    def reject_password_like_keys(cls, value: dict) -> dict:
        blocked = ("senha", "password", "pfx", "private_key", "chave_privada", "certificado")
        serialized_keys = " ".join(str(key).lower() for key in _walk_keys(value))
        if any(token in serialized_keys for token in blocked):
            raise ValueError("storage_state nao pode conter senha/certificado/chave privada")
        return value


class CredencialAssinaturaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    usuario_id: int
    provedor: str
    tribunal: str | None
    sistema: str | None = None
    grau: str | None = None
    tipo: str | None = None
    modo: str
    referencia_vault: str
    ativo: bool
    created_at: datetime
    updated_at: datetime


class TemplatePeticaoCreate(BaseModel):
    tipo: str = Field(min_length=2, max_length=100)
    area: str | None = Field(default=None, max_length=100)
    nome: str = Field(min_length=2, max_length=255)
    conteudo: str = Field(min_length=10)
    ativo: bool = True


class TemplatePeticaoUpdate(BaseModel):
    tipo: str | None = Field(default=None, min_length=2, max_length=100)
    area: str | None = Field(default=None, max_length=100)
    nome: str | None = Field(default=None, min_length=2, max_length=255)
    conteudo: str | None = Field(default=None, min_length=10)
    ativo: bool | None = None


class TemplatePeticaoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    escritorio_id: int
    tipo: str
    area: str | None
    nome: str
    conteudo: str
    ativo: bool
    created_at: datetime
    updated_at: datetime


class AlertaPrazo(BaseModel):
    """Radar de prazo: alerta derivado dos prazos abertos (sem tabela própria)."""

    prazo_id: int
    processo_id: int | None
    processo_numero: str | None
    descricao: str | None
    data_fatal: date
    dias_para_vencer: int
    nivel: Literal["vencido", "d0", "d1", "d3"]


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


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ator: str
    acao: str
    entidade: str | None
    entidade_id: int | None
    detalhe: dict | None
    created_at: datetime


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    processo_id: int | None = None


class ProposedAction(BaseModel):
    tipo: str  # "gerar_minuta" | "marcar_prazo_cumprido" | "aprovar_peticao"
    label: str
    endpoint: str
    metodo: str = "POST"
    payload: dict


class ToolTraceItem(BaseModel):
    ferramenta: str
    input: dict


class ChatResponse(BaseModel):
    reply: str
    proposed_actions: list[ProposedAction] = []
    tool_trace: list[ToolTraceItem] = []


class OabMonitoradaOut(BaseModel):
    id: int
    escritorio_id: int
    oab: str
    uf: str
    ativo: bool
    intervalo_horas: int
    ultima_captura_em: datetime | None = None
    cursor_data: date | None = None

    model_config = {"from_attributes": True}


class OabRemovalResultOut(BaseModel):
    oab_id: int
    oab: str
    uf: str
    purge: bool
    removidos: dict[str, int]


class OabMonitoradaCreate(BaseModel):
    oab: str
    uf: str
    intervalo_horas: int = 12
