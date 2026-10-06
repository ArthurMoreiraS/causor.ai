"""Restrict direct public REST access to the backend-owned SOR.

Revision ID: b8f4a2d7c901
Revises: b7d2c9e4a611
"""

from alembic import op

from app.sor.permissions import LOCKDOWN_SQL

revision = "b8f4a2d7c901"
down_revision = "b7d2c9e4a611"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(LOCKDOWN_SQL)


def downgrade() -> None:
    # The previous ACL is unknown. Never recreate broad public access to data.
    pass
