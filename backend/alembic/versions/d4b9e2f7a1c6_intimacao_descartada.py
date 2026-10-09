"""publicacoes descartadas junto com o processo excluido

Revision ID: d4b9e2f7a1c6
Revises: c1d7e3a9f5b2
Create Date: 2026-10-09
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d4b9e2f7a1c6"
down_revision: Union[str, Sequence[str], None] = "c1d7e3a9f5b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "intimacao_descartada",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("escritorio_id", sa.Integer(), nullable=False),
        sa.Column("fonte", sa.String(length=20), nullable=False),
        sa.Column("fonte_id", sa.String(length=64), nullable=False),
        sa.Column("numero_processo", sa.String(length=30), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["escritorio_id"], ["escritorio.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("escritorio_id", "fonte", "fonte_id", name="uq_intimacao_descartada_fonte"),
    )
    op.create_index(op.f("ix_intimacao_descartada_escritorio_id"), "intimacao_descartada", ["escritorio_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_intimacao_descartada_escritorio_id"), table_name="intimacao_descartada")
    op.drop_table("intimacao_descartada")
