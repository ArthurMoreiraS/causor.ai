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
    with op.batch_alter_table("usuario") as batch_op:
        batch_op.add_column(sa.Column("supabase_user_id", sa.String(length=36), nullable=True))
        batch_op.create_unique_constraint("uq_usuario_supabase_user_id", ["supabase_user_id"])

    for tabela in ("intimacao", "prazo", "peticao"):
        with op.batch_alter_table(tabela) as batch_op:
            batch_op.add_column(sa.Column("escritorio_id", sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                f"fk_{tabela}_escritorio", "escritorio", ["escritorio_id"], ["id"]
            )
            batch_op.create_index(f"ix_{tabela}_escritorio_id", ["escritorio_id"])

    # Backfill via correlated subquery; portable across SQLite and Postgres.
    op.execute(
        "UPDATE prazo SET escritorio_id = ("
        "SELECT p.escritorio_id FROM processo p WHERE p.id = prazo.processo_id"
        ") WHERE processo_id IS NOT NULL"
    )
    op.execute(
        "UPDATE peticao SET escritorio_id = ("
        "SELECT p.escritorio_id FROM processo p WHERE p.id = peticao.processo_id"
        ") WHERE processo_id IS NOT NULL"
    )
    op.execute(
        "UPDATE intimacao SET escritorio_id = ("
        "SELECT p.escritorio_id FROM processo p WHERE p.id = intimacao.processo_id"
        ") WHERE processo_id IS NOT NULL"
    )


def downgrade() -> None:
    for tabela in ("intimacao", "prazo", "peticao"):
        with op.batch_alter_table(tabela) as batch_op:
            batch_op.drop_index(f"ix_{tabela}_escritorio_id")
            batch_op.drop_constraint(f"fk_{tabela}_escritorio", type_="foreignkey")
            batch_op.drop_column("escritorio_id")

    with op.batch_alter_table("usuario") as batch_op:
        batch_op.drop_constraint("uq_usuario_supabase_user_id", type_="unique")
        batch_op.drop_column("supabase_user_id")
