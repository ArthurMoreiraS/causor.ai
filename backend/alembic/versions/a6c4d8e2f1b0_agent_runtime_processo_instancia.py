"""agent runtime and processo instancia

Revision ID: a6c4d8e2f1b0
Revises: f0a1b2c3d4e5
Create Date: 2026-07-10 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a6c4d8e2f1b0"
down_revision: Union[str, Sequence[str], None] = "f0a1b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "processo_instancia",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("processo_id", sa.Integer(), sa.ForeignKey("processo.id"), nullable=False),
        sa.Column("escritorio_id", sa.Integer(), sa.ForeignKey("escritorio.id"), nullable=False),
        sa.Column("sistema", sa.String(length=20), nullable=False),
        sa.Column("tribunal", sa.String(length=50), nullable=False),
        sa.Column("grau", sa.String(length=4), nullable=False),
        sa.Column("url_base", sa.String(length=1024), nullable=True),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "processo_id", "sistema", "tribunal", "grau",
            name="uq_processo_instancia_route",
        ),
    )
    op.create_index(
        "ix_processo_instancia_escritorio_id", "processo_instancia", ["escritorio_id"]
    )

    op.create_table(
        "agent_installation",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("escritorio_id", sa.Integer(), sa.ForeignKey("escritorio.id"), nullable=False),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuario.id"), nullable=False),
        sa.Column("nome", sa.String(length=120), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.String(length=40), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_agent_installation_escritorio_id", "agent_installation", ["escritorio_id"]
    )

    op.create_table(
        "agent_pairing_code",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("escritorio_id", sa.Integer(), sa.ForeignKey("escritorio.id"), nullable=False),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuario.id"), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_agent_pairing_code_escritorio_id", "agent_pairing_code", ["escritorio_id"]
    )

    op.create_table(
        "agent_command",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("escritorio_id", sa.Integer(), sa.ForeignKey("escritorio.id"), nullable=False),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuario.id"), nullable=True),
        sa.Column(
            "installation_id",
            sa.Integer(),
            sa.ForeignKey("agent_installation.id"),
            nullable=True,
        ),
        sa.Column("tipo", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="queued"),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("resultado", sa.JSON(), nullable=True),
        sa.Column("erro_codigo", sa.String(length=80), nullable=True),
        sa.Column("erro_detalhe", sa.Text(), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "escritorio_id", "idempotency_key", name="uq_agent_command_idempotency"
        ),
    )
    op.create_index("ix_agent_command_escritorio_id", "agent_command", ["escritorio_id"])
    op.create_index("ix_agent_command_installation_id", "agent_command", ["installation_id"])
    op.create_index("ix_agent_command_status", "agent_command", ["status"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_agent_command_status", table_name="agent_command")
    op.drop_index("ix_agent_command_installation_id", table_name="agent_command")
    op.drop_index("ix_agent_command_escritorio_id", table_name="agent_command")
    op.drop_table("agent_command")
    op.drop_index("ix_agent_pairing_code_escritorio_id", table_name="agent_pairing_code")
    op.drop_table("agent_pairing_code")
    op.drop_index("ix_agent_installation_escritorio_id", table_name="agent_installation")
    op.drop_table("agent_installation")
    op.drop_index("ix_processo_instancia_escritorio_id", table_name="processo_instancia")
    op.drop_table("processo_instancia")
