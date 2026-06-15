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
    String,
    Text,
    UniqueConstraint,
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


class Intimacao(TimestampMixin, Base):
    """A captured court communication (intimação/comunicação) from DJEN/Comunica."""

    __tablename__ = "intimacao"
    __table_args__ = (
        UniqueConstraint("fonte", "fonte_id", name="uq_intimacao_fonte"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    processo_id: Mapped[int | None] = mapped_column(ForeignKey("processo.id"))
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
    escritorio_id: Mapped[int | None] = mapped_column(ForeignKey("escritorio.id"), index=True)
    tipo: Mapped[str | None] = mapped_column(String(100))
    conteudo: Mapped[str | None] = mapped_column(Text)
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
    __tablename__ = "documento"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    processo_id: Mapped[int | None] = mapped_column(ForeignKey("processo.id"))
    peticao_id: Mapped[int | None] = mapped_column(ForeignKey("peticao.id"))
    nome: Mapped[str] = mapped_column(String(255), nullable=False)
    tipo: Mapped[str | None] = mapped_column(String(50))
    uri: Mapped[str | None] = mapped_column(String(1024))  # storage reference, not contents


class CredencialAssinatura(TimestampMixin, Base):
    """Reference to a signing credential. NEVER stores secrets/passwords.

    Holds only a non-secret reference to the cloud-certificate provider; the
    actual certificate/credential lives in the vault.
    """

    __tablename__ = "credencial_assinatura"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"), nullable=False)
    provedor: Mapped[str] = mapped_column(String(50), nullable=False)  # BirdID/VIDaaS/...
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
