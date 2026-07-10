"""System of Record — core domain models.

These map the entities described in the plan: escritorio, usuario, cliente,
processo, intimacao, prazo, peticao, andamento, documento, credencial_assinatura,
audit_log.

Design notes:
- Column types stay portable (SQLite for unit tests, Postgres in prod).
- Timestamps are timezone-aware UTC.
- ``audit_log`` is append-only by convention (no update/delete in app code);
  immutability is enforced operationally at the DB/grant level.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.sor.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class Escritorio(TimestampMixin, Base):
    __tablename__ = "escritorio"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(255), nullable=False)
    cnpj: Mapped[str | None] = mapped_column(String(20), unique=True)

    # Papel timbrado do escritório aplicado no PDF de protocolo (spec 2026-07-09).
    timbrado_logo: Mapped[bytes | None] = mapped_column(LargeBinary)
    timbrado_logo_mime: Mapped[str | None] = mapped_column(String(30))
    timbrado_cabecalho: Mapped[str | None] = mapped_column(Text)
    timbrado_rodape: Mapped[str | None] = mapped_column(Text)

    usuarios: Mapped[list[Usuario]] = relationship(back_populates="escritorio")
    clientes: Mapped[list[Cliente]] = relationship(back_populates="escritorio")
    processos: Mapped[list[Processo]] = relationship(back_populates="escritorio")


class Usuario(TimestampMixin, Base):
    __tablename__ = "usuario"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    escritorio_id: Mapped[int] = mapped_column(ForeignKey("escritorio.id"), nullable=False)
    nome: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    oab: Mapped[str | None] = mapped_column(String(20), index=True)
    oab_uf: Mapped[str | None] = mapped_column(String(2))
    supabase_user_id: Mapped[str | None] = mapped_column(String(36), unique=True)

    escritorio: Mapped[Escritorio] = relationship(back_populates="usuarios")


class OabMonitorada(TimestampMixin, Base):
    """An OAB registration polled on a schedule for new intimações (DJEN)."""

    __tablename__ = "oab_monitorada"
    __table_args__ = (
        UniqueConstraint("escritorio_id", "oab", "uf", name="uq_oab_monitorada"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    escritorio_id: Mapped[int] = mapped_column(ForeignKey("escritorio.id"), nullable=False)
    oab: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    uf: Mapped[str] = mapped_column(String(2), nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    intervalo_horas: Mapped[int] = mapped_column(Integer, default=12)
    ultima_captura_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cursor_data: Mapped[date | None] = mapped_column(Date)


class Cliente(TimestampMixin, Base):
    __tablename__ = "cliente"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    escritorio_id: Mapped[int] = mapped_column(ForeignKey("escritorio.id"), nullable=False)
    nome: Mapped[str] = mapped_column(String(255), nullable=False)
    documento: Mapped[str | None] = mapped_column(String(20))

    escritorio: Mapped[Escritorio] = relationship(back_populates="clientes")
    processos: Mapped[list[Processo]] = relationship(back_populates="cliente")


class Processo(TimestampMixin, Base):
    __tablename__ = "processo"
    __table_args__ = (UniqueConstraint("escritorio_id", "numero", name="uq_processo_numero"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    escritorio_id: Mapped[int] = mapped_column(ForeignKey("escritorio.id"), nullable=False)
    cliente_id: Mapped[int | None] = mapped_column(ForeignKey("cliente.id"))
    numero: Mapped[str] = mapped_column(String(30), nullable=False, index=True)  # CNJ format
    classe: Mapped[str | None] = mapped_column(String(255))
    tribunal: Mapped[str | None] = mapped_column(String(50))
    orgao_julgador: Mapped[str | None] = mapped_column(String(255))
    sistema: Mapped[str | None] = mapped_column(String(50))  # PJe / e-SAJ / Projudi / EPROC
    data_ajuizamento: Mapped[date | None] = mapped_column(Date)

    escritorio: Mapped[Escritorio] = relationship(back_populates="processos")
    cliente: Mapped[Cliente | None] = relationship(back_populates="processos")
    intimacoes: Mapped[list[Intimacao]] = relationship(back_populates="processo")
    prazos: Mapped[list[Prazo]] = relationship(back_populates="processo")
    andamentos: Mapped[list[Andamento]] = relationship(back_populates="processo")
    peticoes: Mapped[list[Peticao]] = relationship(back_populates="processo")
    instancias: Mapped[list[ProcessoInstancia]] = relationship(
        back_populates="processo", cascade="all, delete-orphan"
    )


class ProcessoInstancia(TimestampMixin, Base):
    """One degree (1º/2º grau) of a processo in a specific court system.

    A processo can live in more than one system/degree at once (e.g. 1º grau
    in PJe and 2º grau in e-SAJ); never assume a single grau on Processo.
    """

    __tablename__ = "processo_instancia"
    __table_args__ = (
        UniqueConstraint(
            "processo_id", "sistema", "tribunal", "grau",
            name="uq_processo_instancia_route",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    processo_id: Mapped[int] = mapped_column(ForeignKey("processo.id"), nullable=False)
    escritorio_id: Mapped[int] = mapped_column(
        ForeignKey("escritorio.id"), nullable=False, index=True
    )
    sistema: Mapped[str] = mapped_column(String(20), nullable=False)
    tribunal: Mapped[str] = mapped_column(String(50), nullable=False)
    grau: Mapped[str] = mapped_column(String(4), nullable=False)
    url_base: Mapped[str | None] = mapped_column(String(1024))
    external_id: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")

    processo: Mapped[Processo] = relationship(back_populates="instancias")


class AgentInstallation(TimestampMixin, Base):
    """A paired local agent (lawyer's machine). Token stored as SHA-256 only."""

    __tablename__ = "agent_installation"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    escritorio_id: Mapped[int] = mapped_column(
        ForeignKey("escritorio.id"), nullable=False, index=True
    )
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"), nullable=False)
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[str | None] = mapped_column(String(40))


class AgentPairingCode(TimestampMixin, Base):
    """One-time pairing code (10 min expiry). Stored hashed, never raw."""

    __tablename__ = "agent_pairing_code"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    escritorio_id: Mapped[int] = mapped_column(
        ForeignKey("escritorio.id"), nullable=False, index=True
    )
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"), nullable=False)
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AgentCommand(TimestampMixin, Base):
    """Idempotent command published by the backend for a local agent.

    Payload/resultado never contain secrets (sessions, cookies, certificates);
    the authenticated session lives only on the agent machine.
    """

    __tablename__ = "agent_command"
    __table_args__ = (
        UniqueConstraint(
            "escritorio_id", "idempotency_key", name="uq_agent_command_idempotency"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    escritorio_id: Mapped[int] = mapped_column(
        ForeignKey("escritorio.id"), nullable=False, index=True
    )
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))
    installation_id: Mapped[int | None] = mapped_column(
        ForeignKey("agent_installation.id"), index=True
    )
    tipo: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="queued", index=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    resultado: Mapped[dict | None] = mapped_column(JSON)
    erro_codigo: Mapped[str | None] = mapped_column(String(80))
    erro_detalhe: Mapped[str | None] = mapped_column(Text)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Intimacao(TimestampMixin, Base):
    """A captured court communication (intimação/comunicação) from DJEN/Comunica."""

    __tablename__ = "intimacao"
    __table_args__ = (
        UniqueConstraint("fonte", "fonte_id", name="uq_intimacao_fonte"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    processo_id: Mapped[int | None] = mapped_column(ForeignKey("processo.id"))
    # Tenant desnormalizado. Nullable só durante a transição (backfill na migração
    # e2... + capture carimbando); leituras já filtram por ele.
    escritorio_id: Mapped[int | None] = mapped_column(ForeignKey("escritorio.id"), index=True)
    fonte: Mapped[str] = mapped_column(String(20), nullable=False, default="DJEN")
    fonte_id: Mapped[str] = mapped_column(String(64), nullable=False)  # external dedupe key
    numero_processo: Mapped[str | None] = mapped_column(String(30), index=True)
    tribunal: Mapped[str | None] = mapped_column(String(50))
    tipo_comunicacao: Mapped[str | None] = mapped_column(String(100))
    teor: Mapped[str | None] = mapped_column(Text)
    data_disponibilizacao: Mapped[date | None] = mapped_column(Date)
    data_publicacao: Mapped[date | None] = mapped_column(Date)
    payload: Mapped[dict | None] = mapped_column(JSON)

    processo: Mapped[Processo | None] = relationship(back_populates="intimacoes")
    prazos: Mapped[list[Prazo]] = relationship(back_populates="intimacao")


class Prazo(TimestampMixin, Base):
    __tablename__ = "prazo"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    processo_id: Mapped[int | None] = mapped_column(ForeignKey("processo.id"))
    intimacao_id: Mapped[int | None] = mapped_column(ForeignKey("intimacao.id"))
    # Tenant desnormalizado. Nullable só durante a transição (backfill na migração).
    escritorio_id: Mapped[int | None] = mapped_column(ForeignKey("escritorio.id"), index=True)
    descricao: Mapped[str | None] = mapped_column(String(255))
    data_inicio: Mapped[date] = mapped_column(Date, nullable=False)  # publication base
    dias: Mapped[int] = mapped_column(Integer, nullable=False)
    dias_uteis: Mapped[bool] = mapped_column(Boolean, default=True)
    data_fatal: Mapped[date] = mapped_column(Date, nullable=False)
    cumprido: Mapped[bool] = mapped_column(Boolean, default=False)

    processo: Mapped[Processo | None] = relationship(back_populates="prazos")
    intimacao: Mapped[Intimacao | None] = relationship(back_populates="prazos")


class Peticao(TimestampMixin, Base):
    __tablename__ = "peticao"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    processo_id: Mapped[int] = mapped_column(ForeignKey("processo.id"), nullable=False)
    prazo_id: Mapped[int | None] = mapped_column(ForeignKey("prazo.id"))
    # Tenant desnormalizado. Nullable só durante a transição (backfill na migração).
    escritorio_id: Mapped[int | None] = mapped_column(ForeignKey("escritorio.id"), index=True)
    tipo: Mapped[str | None] = mapped_column(String(100))
    conteudo: Mapped[str | None] = mapped_column(Text)
    # Dossiê de apoio gerado junto com a minuta (contexto consolidado, análise da
    # providência, alertas e confiança). Fica separado de `conteudo` para manter a
    # minuta protocolo-limpa. É conteúdo processual, nunca segredo (vault-only rule).
    dossie: Mapped[dict | None] = mapped_column(JSON)
    # human approval gate before any irreversible filing
    status: Mapped[str] = mapped_column(String(30), default="rascunho")  # rascunho/aprovada/protocolada
    aprovada_por: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))
    protocolada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    processo: Mapped[Processo] = relationship(back_populates="peticoes")


class TemplatePeticao(TimestampMixin, Base):
    """Office-owned drafting template for repeatable petition types."""

    __tablename__ = "template_peticao"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    escritorio_id: Mapped[int] = mapped_column(ForeignKey("escritorio.id"), nullable=False)
    tipo: Mapped[str] = mapped_column(String(100), nullable=False)
    area: Mapped[str | None] = mapped_column(String(100))
    nome: Mapped[str] = mapped_column(String(255), nullable=False)
    conteudo: Mapped[str] = mapped_column(Text, nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)


class Andamento(TimestampMixin, Base):
    """A process movement (from DataJud movimentos[])."""

    __tablename__ = "andamento"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    processo_id: Mapped[int] = mapped_column(ForeignKey("processo.id"), nullable=False)
    codigo: Mapped[int | None] = mapped_column(Integer)
    descricao: Mapped[str | None] = mapped_column(String(500))
    data: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    processo: Mapped[Processo] = relationship(back_populates="andamentos")


class Documento(TimestampMixin, Base):
    """Documento lógico dos autos (identidade estável no portal).

    O conteúdo/versões ficam em `DocumentoArquivo` (imutáveis por SHA-256).
    Colunas de identidade são nullable para documentos legados/demo.
    """

    __tablename__ = "documento"
    __table_args__ = (
        UniqueConstraint("processo_instancia_id", "external_id", name="uq_documento_external"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    processo_id: Mapped[int | None] = mapped_column(ForeignKey("processo.id"))
    peticao_id: Mapped[int | None] = mapped_column(ForeignKey("peticao.id"))
    escritorio_id: Mapped[int | None] = mapped_column(ForeignKey("escritorio.id"), index=True)
    processo_instancia_id: Mapped[int | None] = mapped_column(
        ForeignKey("processo_instancia.id"), index=True
    )
    external_id: Mapped[str | None] = mapped_column(String(255))
    parent_external_id: Mapped[str | None] = mapped_column(String(255))
    nome: Mapped[str] = mapped_column(String(255), nullable=False)
    tipo: Mapped[str | None] = mapped_column(String(50))
    uri: Mapped[str | None] = mapped_column(String(1024))  # storage reference, not contents
    ordem: Mapped[int | None] = mapped_column(Integer)
    data_documento: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sigiloso: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    metadados: Mapped[dict | None] = mapped_column(JSON)


class CapturaAutos(TimestampMixin, Base):
    """Uma geração de captura integral dos autos de uma instância.

    `status=complete` significa integridade binária provada: enumeração
    inicial == enumeração final e todo item com versão verificada.
    """

    __tablename__ = "captura_autos"
    __table_args__ = (
        UniqueConstraint(
            "processo_instancia_id", "generation", name="uq_captura_autos_generation"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    escritorio_id: Mapped[int] = mapped_column(
        ForeignKey("escritorio.id"), nullable=False, index=True
    )
    processo_instancia_id: Mapped[int] = mapped_column(
        ForeignKey("processo_instancia.id"), nullable=False, index=True
    )
    agent_command_id: Mapped[int | None] = mapped_column(ForeignKey("agent_command.id"))
    generation: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="queued", index=True)
    initial_fingerprint: Mapped[str | None] = mapped_column(String(71))
    final_fingerprint: Mapped[str | None] = mapped_column(String(71))
    expected_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    captured_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    missing_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cursor_complete: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    error_code: Mapped[str | None] = mapped_column(String(80))
    evidence: Mapped[dict | None] = mapped_column(JSON)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DocumentoArquivo(TimestampMixin, Base):
    """Versão imutável (por SHA-256) de um documento lógico."""

    __tablename__ = "documento_arquivo"
    __table_args__ = (
        UniqueConstraint("documento_id", "sha256", name="uq_documento_arquivo_hash"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    documento_id: Mapped[int] = mapped_column(
        ForeignKey("documento.id"), nullable=False, index=True
    )
    captura_id: Mapped[int] = mapped_column(
        ForeignKey("captura_autos.id"), nullable=False, index=True
    )
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    uri: Mapped[str] = mapped_column(String(1024), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    page_count: Mapped[int | None] = mapped_column(Integer)
    text_sha256: Mapped[str | None] = mapped_column(String(64))
    extraction_status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    extraction_error: Mapped[str | None] = mapped_column(Text)
    atual: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)


class ManifestoItem(TimestampMixin, Base):
    """Item da enumeração de uma captura; liga documento lógico à versão baixada."""

    __tablename__ = "manifesto_item"
    __table_args__ = (
        UniqueConstraint("captura_id", "external_id", name="uq_manifesto_item_external"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    captura_id: Mapped[int] = mapped_column(
        ForeignKey("captura_autos.id"), nullable=False, index=True
    )
    documento_id: Mapped[int] = mapped_column(ForeignKey("documento.id"), nullable=False)
    documento_arquivo_id: Mapped[int | None] = mapped_column(ForeignKey("documento_arquivo.id"))
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    ordem: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    error_code: Mapped[str | None] = mapped_column(String(80))


class DocumentoTrecho(TimestampMixin, Base):
    """Trecho citável de uma página; unidade canônica de citação."""

    __tablename__ = "documento_trecho"
    __table_args__ = (
        UniqueConstraint(
            "documento_arquivo_id", "pagina", "indice", name="uq_documento_trecho_posicao"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    documento_arquivo_id: Mapped[int] = mapped_column(
        ForeignKey("documento_arquivo.id"), nullable=False, index=True
    )
    pagina: Mapped[int] = mapped_column(Integer, nullable=False)
    indice: Mapped[int] = mapped_column(Integer, nullable=False)
    texto: Mapped[str] = mapped_column(Text, nullable=False)
    texto_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False)
    ocr: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class DocumentoResumo(TimestampMixin, Base):
    """Resumo estruturado (com citações validadas) de uma versão de documento."""

    __tablename__ = "documento_resumo"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    documento_arquivo_id: Mapped[int] = mapped_column(
        ForeignKey("documento_arquivo.id"), nullable=False, unique=True
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    resumo: Mapped[str | None] = mapped_column(Text)
    dados: Mapped[dict | None] = mapped_column(JSON)
    citations: Mapped[list | None] = mapped_column(JSON)
    model: Mapped[str | None] = mapped_column(String(100))
    error: Mapped[str | None] = mapped_column(Text)


class ContextoProcesso(TimestampMixin, Base):
    """Contexto integral e citado do processo; `ready` exige cobertura total."""

    __tablename__ = "contexto_processo"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    escritorio_id: Mapped[int] = mapped_column(
        ForeignKey("escritorio.id"), nullable=False, index=True
    )
    processo_id: Mapped[int] = mapped_column(
        ForeignKey("processo.id"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="building")
    source_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    inventario: Mapped[list] = mapped_column(JSON, nullable=False)
    cobertura: Mapped[dict] = mapped_column(JSON, nullable=False)
    contexto_consolidado: Mapped[str | None] = mapped_column(Text)
    citations: Mapped[list | None] = mapped_column(JSON)
    ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ContextOverride(TimestampMixin, Base):
    """Liberação excepcional (uso único, 30 min) de contexto incompleto."""

    __tablename__ = "context_override"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    escritorio_id: Mapped[int] = mapped_column(
        ForeignKey("escritorio.id"), nullable=False, index=True
    )
    processo_id: Mapped[int] = mapped_column(
        ForeignKey("processo.id"), nullable=False, index=True
    )
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"), nullable=False)
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    justification: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CredencialAssinatura(TimestampMixin, Base):
    """Reference to a signing credential. NEVER stores secrets/passwords.

    Holds only a non-secret reference to the cloud-certificate provider; the
    actual certificate/credential lives in the vault.
    """

    __tablename__ = "credencial_assinatura"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"), nullable=False)
    provedor: Mapped[str] = mapped_column(String(50), nullable=False)  # BirdID/VIDaaS/...
    # Tribunal the session/credencial was captured for (e.g. "TJSP"); null for
    # cloud cert references. Metadata only, not a secret.
    tribunal: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Processing system (PJe/e-SAJ/EPROC/Projudi) and grau (1/2) the session
    # belongs to; null for cloud cert references. Routes filing to the session.
    sistema: Mapped[str | None] = mapped_column(String(20), nullable=True)
    grau: Mapped[str | None] = mapped_column(String(4), nullable=True)
    # Credential kind: "session" (court cookie) | "cloud_cert" (push-signing ref).
    tipo: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="session",
        server_default=text("'session'"),
    )
    # How the lawyer signs: manual_handoff (signs outside Causor) | api | local_agent.
    modo: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="manual_handoff",
        server_default=text("'manual_handoff'"),
    )
    referencia_vault: Mapped[str] = mapped_column(String(255), nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)


class JobExecucao(TimestampMixin, Base):
    """Async workflow/job state tracked in the SOR.

    Jobs make long-running actions observable before we add a real worker.
    Payload/result must never contain secrets.
    """

    __tablename__ = "job_execucao"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tipo: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="queued")
    entidade: Mapped[str | None] = mapped_column(String(50))
    entidade_id: Mapped[int | None] = mapped_column(Integer)
    payload: Mapped[dict | None] = mapped_column(JSON)
    resultado: Mapped[dict | None] = mapped_column(JSON)
    erro: Mapped[str | None] = mapped_column(Text)


class AuditLog(Base):
    """Immutable, append-only audit trail. No updated_at — entries never change."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    escritorio_id: Mapped[int | None] = mapped_column(ForeignKey("escritorio.id"))
    ator: Mapped[str] = mapped_column(String(100), nullable=False)  # usuario:ID / agent / system
    acao: Mapped[str] = mapped_column(String(100), nullable=False)
    entidade: Mapped[str | None] = mapped_column(String(50))
    entidade_id: Mapped[int | None] = mapped_column(Integer)
    detalhe: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
