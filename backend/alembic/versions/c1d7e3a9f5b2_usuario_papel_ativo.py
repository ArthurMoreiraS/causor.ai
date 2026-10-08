"""papel e ativo do usuario (equipe do escritorio)

Revision ID: c1d7e3a9f5b2
Revises: b8f4a2d7c901
Create Date: 2026-10-07
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c1d7e3a9f5b2"
down_revision: Union[str, Sequence[str], None] = "b8f4a2d7c901"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "usuario",
        sa.Column("papel", sa.String(length=20), server_default="advogado", nullable=False),
    )
    op.add_column(
        "usuario",
        sa.Column("ativo", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )
    op.create_check_constraint(
        "ck_usuario_papel", "usuario", "papel IN ('administrador', 'advogado', 'assistente')"
    )
    # Quem já tinha acesso era dono da conta: continua podendo tudo.
    op.execute("UPDATE usuario SET papel = 'administrador'")


def downgrade() -> None:
    op.drop_constraint("ck_usuario_papel", "usuario", type_="check")
    op.drop_column("usuario", "ativo")
    op.drop_column("usuario", "papel")
