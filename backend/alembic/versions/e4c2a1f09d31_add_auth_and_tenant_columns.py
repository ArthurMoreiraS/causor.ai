"""add auth and tenant columns

Revision ID: e4c2a1f09d31
Revises: d3b1c0f5a9e2
Create Date: 2026-06-15
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "e4c2a1f09d31"
down_revision: Union[str, Sequence[str], None] = "d3b1c0f5a9e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("usuario", sa.Column("supabase_user_id", sa.String(length=36), nullable=True))
    op.create_unique_constraint("uq_usuario_supabase_user_id", "usuario", ["supabase_user_id"])

    for tabela in ("intimacao", "prazo", "peticao"):
        op.add_column(tabela, sa.Column("escritorio_id", sa.Integer(), nullable=True))
        op.create_foreign_key(
            f"fk_{tabela}_escritorio", tabela, "escritorio", ["escritorio_id"], ["id"]
        )
        op.create_index(f"ix_{tabela}_escritorio_id", tabela, ["escritorio_id"])

    # Backfill via join no processo (Postgres).
    op.execute(
        "UPDATE prazo SET escritorio_id = p.escritorio_id "
        "FROM processo p WHERE prazo.processo_id = p.id"
    )
    op.execute(
        "UPDATE peticao SET escritorio_id = p.escritorio_id "
        "FROM processo p WHERE peticao.processo_id = p.id"
    )
    op.execute(
        "UPDATE intimacao SET escritorio_id = p.escritorio_id "
        "FROM processo p WHERE intimacao.processo_id = p.id"
    )


def downgrade() -> None:
    for tabela in ("intimacao", "prazo", "peticao"):
        op.drop_index(f"ix_{tabela}_escritorio_id", table_name=tabela)
        op.drop_constraint(f"fk_{tabela}_escritorio", tabela, type_="foreignkey")
        op.drop_column(tabela, "escritorio_id")
    op.drop_constraint("uq_usuario_supabase_user_id", "usuario", type_="unique")
    op.drop_column("usuario", "supabase_user_id")
