"""add oab_monitorada

Revision ID: d3b1c0f5a9e2
Revises: c2a4d9e8f013
Create Date: 2026-06-13 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d3b1c0f5a9e2"
down_revision: Union[str, Sequence[str], None] = "c2a4d9e8f013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "oab_monitorada",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("escritorio_id", sa.Integer(), nullable=False),
        sa.Column("oab", sa.String(length=20), nullable=False),
        sa.Column("uf", sa.String(length=2), nullable=False),
        sa.Column("ativo", sa.Boolean(), nullable=False),
        sa.Column("intervalo_horas", sa.Integer(), nullable=False),
        sa.Column("ultima_captura_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cursor_data", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["escritorio_id"], ["escritorio.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("escritorio_id", "oab", "uf", name="uq_oab_monitorada"),
    )
    op.create_index("ix_oab_monitorada_oab", "oab_monitorada", ["oab"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_oab_monitorada_oab", table_name="oab_monitorada")
    op.drop_table("oab_monitorada")
