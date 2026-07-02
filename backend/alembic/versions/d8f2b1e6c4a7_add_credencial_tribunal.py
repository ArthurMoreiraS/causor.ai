"""add tribunal to credencial_assinatura

Adds an optional ``tribunal`` column to ``credencial_assinatura`` so the UI can
show which tribunal a PJeSession credential was captured for (e.g. "PJe - TJSP").
The column is nullable; cloud-certificate references leave it null. Tribunal is
metadata only, not a secret.

Revision ID: d8f2b1e6c4a7
Revises: c7e1a9b3d2f4
Create Date: 2026-07-02 03:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "d8f2b1e6c4a7"
down_revision: Union[str, Sequence[str], None] = "c7e1a9b3d2f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("credencial_assinatura") as batch_op:
        batch_op.add_column(sa.Column("tribunal", sa.String(length=50), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("credencial_assinatura") as batch_op:
        batch_op.drop_column("tribunal")
