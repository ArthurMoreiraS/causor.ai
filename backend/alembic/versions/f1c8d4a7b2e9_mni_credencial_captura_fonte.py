"""mni credencial + captura fonte

Revision ID: f1c8d4a7b2e9
Revises: c9f7a1b5d4e3
Create Date: 2026-07-21
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f1c8d4a7b2e9"
down_revision: Union[str, Sequence[str], None] = "c9f7a1b5d4e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "mni_credencial",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "escritorio_id",
            sa.Integer(),
            sa.ForeignKey("escritorio.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("tribunal", sa.String(length=50), nullable=False),
        sa.Column("id_consultante", sa.String(length=120), nullable=False),
        sa.Column("referencia_vault", sa.String(length=255), nullable=False),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_by_usuario_id",
            sa.Integer(),
            sa.ForeignKey("usuario.id"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("escritorio_id", "tribunal", name="uq_mni_credencial_tribunal"),
    )
    op.add_column(
        "captura_autos",
        sa.Column("fonte", sa.String(length=10), nullable=False, server_default="agente"),
    )


def downgrade() -> None:
    op.drop_column("captura_autos", "fonte")
    op.drop_table("mni_credencial")
