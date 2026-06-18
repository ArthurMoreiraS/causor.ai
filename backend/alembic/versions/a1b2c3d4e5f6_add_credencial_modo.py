"""add modo to credencial_assinatura

Adds the signature-handoff mode (manual_handoff | api | local_agent) to
credencial_assinatura. The column is NOT NULL with a server_default of
'manual_handoff', so the ADD COLUMN fills any pre-existing row (including
PJeSession credentials) without a separate backfill UPDATE.

Revision ID: a1b2c3d4e5f6
Revises: f5d8e3a2b1c4
Create Date: 2026-06-18
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "f5d8e3a2b1c4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("credencial_assinatura") as batch_op:
        batch_op.add_column(
            sa.Column(
                "modo",
                sa.String(length=20),
                nullable=False,
                server_default="manual_handoff",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("credencial_assinatura") as batch_op:
        batch_op.drop_column("modo")
