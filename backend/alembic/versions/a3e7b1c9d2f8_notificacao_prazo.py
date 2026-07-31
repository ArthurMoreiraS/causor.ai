"""notificacao de prazo (dedupe por prazo/nivel)

Revision ID: a3e7b1c9d2f8
Revises: f1c8d4a7b2e9
Create Date: 2026-07-30
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a3e7b1c9d2f8"
down_revision: Union[str, Sequence[str], None] = "f1c8d4a7b2e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notificacao_prazo",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "escritorio_id",
            sa.Integer(),
            sa.ForeignKey("escritorio.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("prazo_id", sa.Integer(), sa.ForeignKey("prazo.id"), nullable=False),
        sa.Column("nivel", sa.String(length=10), nullable=False),
        sa.Column("destino", sa.String(length=500), nullable=False),
        sa.Column("enviado_em", sa.DateTime(timezone=True), nullable=False),
        # O aviso sai uma vez por prazo e por nivel (D-3, D-1, D-0, vencido):
        # a unicidade e o que impede o cron de repetir o mesmo e-mail.
        sa.UniqueConstraint("prazo_id", "nivel", name="uq_notificacao_prazo_nivel"),
    )


def downgrade() -> None:
    op.drop_table("notificacao_prazo")
