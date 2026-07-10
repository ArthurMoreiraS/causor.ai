"""autos integrais e contexto citado

Revision ID: b7d5e9f3a2c1
Revises: a6c4d8e2f1b0
Create Date: 2026-07-10 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b7d5e9f3a2c1"
down_revision: Union[str, Sequence[str], None] = "a6c4d8e2f1b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # -- Documento: identidade de portal (nullable para legado/demo) ---------
    op.add_column(
        "documento", sa.Column("escritorio_id", sa.Integer(), sa.ForeignKey("escritorio.id"))
    )
    op.add_column(
        "documento",
        sa.Column(
            "processo_instancia_id", sa.Integer(), sa.ForeignKey("processo_instancia.id")
        ),
    )
    op.add_column("documento", sa.Column("external_id", sa.String(length=255), nullable=True))
    op.add_column(
        "documento", sa.Column("parent_external_id", sa.String(length=255), nullable=True)
    )
    op.add_column("documento", sa.Column("ordem", sa.Integer(), nullable=True))
    op.add_column(
        "documento", sa.Column("data_documento", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "documento",
        sa.Column("sigiloso", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column("documento", sa.Column("metadados", sa.JSON(), nullable=True))
    op.create_index("ix_documento_escritorio_id", "documento", ["escritorio_id"])
    op.create_index(
        "ix_documento_processo_instancia_id", "documento", ["processo_instancia_id"]
    )
    op.create_unique_constraint(
        "uq_documento_external", "documento", ["processo_instancia_id", "external_id"]
    )

    # Backfill do tenant de documentos legados via processo e, na falta, peticao.
    op.execute(
        """
        update documento
        set escritorio_id = processo.escritorio_id
        from processo
        where documento.processo_id = processo.id
          and documento.escritorio_id is null
        """
    )
    op.execute(
        """
        update documento
        set escritorio_id = processo.escritorio_id
        from peticao
        join processo on processo.id = peticao.processo_id
        where documento.peticao_id = peticao.id
          and documento.escritorio_id is null
        """
    )

    # -- captura_autos --------------------------------------------------------
    op.create_table(
        "captura_autos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("escritorio_id", sa.Integer(), sa.ForeignKey("escritorio.id"), nullable=False),
        sa.Column(
            "processo_instancia_id",
            sa.Integer(),
            sa.ForeignKey("processo_instancia.id"),
            nullable=False,
        ),
        sa.Column("agent_command_id", sa.Integer(), sa.ForeignKey("agent_command.id")),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="queued"),
        sa.Column("initial_fingerprint", sa.String(length=71), nullable=True),
        sa.Column("final_fingerprint", sa.String(length=71), nullable=True),
        sa.Column("expected_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("captured_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("missing_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "cursor_complete", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("evidence", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "processo_instancia_id", "generation", name="uq_captura_autos_generation"
        ),
    )
    op.create_index("ix_captura_autos_escritorio_id", "captura_autos", ["escritorio_id"])
    op.create_index(
        "ix_captura_autos_processo_instancia_id", "captura_autos", ["processo_instancia_id"]
    )
    op.create_index("ix_captura_autos_status", "captura_autos", ["status"])

    # -- documento_arquivo ----------------------------------------------------
    op.create_table(
        "documento_arquivo",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("documento_id", sa.Integer(), sa.ForeignKey("documento.id"), nullable=False),
        sa.Column("captura_id", sa.Integer(), sa.ForeignKey("captura_autos.id"), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("storage_key", sa.String(length=1024), nullable=False),
        sa.Column("uri", sa.String(length=1024), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("text_sha256", sa.String(length=64), nullable=True),
        sa.Column(
            "extraction_status", sa.String(length=30), nullable=False, server_default="pending"
        ),
        sa.Column("extraction_error", sa.Text(), nullable=True),
        sa.Column("atual", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("documento_id", "sha256", name="uq_documento_arquivo_hash"),
    )
    op.create_index("ix_documento_arquivo_documento_id", "documento_arquivo", ["documento_id"])
    op.create_index("ix_documento_arquivo_captura_id", "documento_arquivo", ["captura_id"])
    op.create_index("ix_documento_arquivo_atual", "documento_arquivo", ["atual"])

    # -- manifesto_item -------------------------------------------------------
    op.create_table(
        "manifesto_item",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("captura_id", sa.Integer(), sa.ForeignKey("captura_autos.id"), nullable=False),
        sa.Column("documento_id", sa.Integer(), sa.ForeignKey("documento.id"), nullable=False),
        sa.Column(
            "documento_arquivo_id", sa.Integer(), sa.ForeignKey("documento_arquivo.id")
        ),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("ordem", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("captura_id", "external_id", name="uq_manifesto_item_external"),
    )
    op.create_index("ix_manifesto_item_captura_id", "manifesto_item", ["captura_id"])

    # -- documento_trecho -----------------------------------------------------
    op.create_table(
        "documento_trecho",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "documento_arquivo_id",
            sa.Integer(),
            sa.ForeignKey("documento_arquivo.id"),
            nullable=False,
        ),
        sa.Column("pagina", sa.Integer(), nullable=False),
        sa.Column("indice", sa.Integer(), nullable=False),
        sa.Column("texto", sa.Text(), nullable=False),
        sa.Column("texto_sha256", sa.String(length=64), nullable=False),
        sa.Column("char_count", sa.Integer(), nullable=False),
        sa.Column("ocr", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "documento_arquivo_id", "pagina", "indice", name="uq_documento_trecho_posicao"
        ),
    )
    op.create_index(
        "ix_documento_trecho_documento_arquivo_id", "documento_trecho", ["documento_arquivo_id"]
    )

    # -- documento_resumo -----------------------------------------------------
    op.create_table(
        "documento_resumo",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "documento_arquivo_id",
            sa.Integer(),
            sa.ForeignKey("documento_arquivo.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("resumo", sa.Text(), nullable=True),
        sa.Column("dados", sa.JSON(), nullable=True),
        sa.Column("citations", sa.JSON(), nullable=True),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # -- contexto_processo ----------------------------------------------------
    op.create_table(
        "contexto_processo",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("escritorio_id", sa.Integer(), sa.ForeignKey("escritorio.id"), nullable=False),
        sa.Column("processo_id", sa.Integer(), sa.ForeignKey("processo.id"), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="building"),
        sa.Column("source_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("inventario", sa.JSON(), nullable=False),
        sa.Column("cobertura", sa.JSON(), nullable=False),
        sa.Column("contexto_consolidado", sa.Text(), nullable=True),
        sa.Column("citations", sa.JSON(), nullable=True),
        sa.Column("ready_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_contexto_processo_escritorio_id", "contexto_processo", ["escritorio_id"])
    op.create_index("ix_contexto_processo_processo_id", "contexto_processo", ["processo_id"])

    # -- context_override -----------------------------------------------------
    op.create_table(
        "context_override",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("escritorio_id", sa.Integer(), sa.ForeignKey("escritorio.id"), nullable=False),
        sa.Column("processo_id", sa.Integer(), sa.ForeignKey("processo.id"), nullable=False),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuario.id"), nullable=False),
        sa.Column("action", sa.String(length=30), nullable=False),
        sa.Column("justification", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_context_override_escritorio_id", "context_override", ["escritorio_id"])
    op.create_index("ix_context_override_processo_id", "context_override", ["processo_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_context_override_processo_id", table_name="context_override")
    op.drop_index("ix_context_override_escritorio_id", table_name="context_override")
    op.drop_table("context_override")
    op.drop_index("ix_contexto_processo_processo_id", table_name="contexto_processo")
    op.drop_index("ix_contexto_processo_escritorio_id", table_name="contexto_processo")
    op.drop_table("contexto_processo")
    op.drop_table("documento_resumo")
    op.drop_index(
        "ix_documento_trecho_documento_arquivo_id", table_name="documento_trecho"
    )
    op.drop_table("documento_trecho")
    op.drop_index("ix_manifesto_item_captura_id", table_name="manifesto_item")
    op.drop_table("manifesto_item")
    op.drop_index("ix_documento_arquivo_atual", table_name="documento_arquivo")
    op.drop_index("ix_documento_arquivo_captura_id", table_name="documento_arquivo")
    op.drop_index("ix_documento_arquivo_documento_id", table_name="documento_arquivo")
    op.drop_table("documento_arquivo")
    op.drop_index("ix_captura_autos_status", table_name="captura_autos")
    op.drop_index("ix_captura_autos_processo_instancia_id", table_name="captura_autos")
    op.drop_index("ix_captura_autos_escritorio_id", table_name="captura_autos")
    op.drop_table("captura_autos")
    op.drop_constraint("uq_documento_external", "documento", type_="unique")
    op.drop_index("ix_documento_processo_instancia_id", table_name="documento")
    op.drop_index("ix_documento_escritorio_id", table_name="documento")
    op.drop_column("documento", "metadados")
    op.drop_column("documento", "sigiloso")
    op.drop_column("documento", "data_documento")
    op.drop_column("documento", "ordem")
    op.drop_column("documento", "parent_external_id")
    op.drop_column("documento", "external_id")
    op.drop_column("documento", "processo_instancia_id")
    op.drop_column("documento", "escritorio_id")
