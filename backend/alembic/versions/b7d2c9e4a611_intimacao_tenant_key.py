"""Scope DJEN communication identity to the office.

Revision ID: b7d2c9e4a611
Revises: b0d6e2f8a4c7
"""

from alembic import op
from sqlalchemy import text

revision = "b7d2c9e4a611"
down_revision = "b0d6e2f8a4c7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("uq_intimacao_fonte", "intimacao", type_="unique")
    op.create_unique_constraint(
        "uq_intimacao_tenant_fonte", "intimacao", ["escritorio_id", "fonte", "fonte_id"]
    )


def downgrade() -> None:
    duplicates = op.get_bind().execute(text(
        "SELECT fonte, fonte_id FROM intimacao GROUP BY fonte, fonte_id HAVING count(*) > 1 LIMIT 1"
    )).first()
    if duplicates:
        raise RuntimeError("Downgrade bloquearia intimacoes de escritorios distintos com a mesma fonte")
    op.drop_constraint("uq_intimacao_tenant_fonte", "intimacao", type_="unique")
    op.create_unique_constraint("uq_intimacao_fonte", "intimacao", ["fonte", "fonte_id"])
