"""Add renewable ownership to document jobs.

Revision ID: a5f1b7d3c9e2
Revises: a4d9e2c7b6f1
"""

from alembic import op
import sqlalchemy as sa

revision = "a5f1b7d3c9e2"
down_revision = "a4d9e2c7b6f1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("job_execucao", sa.Column("lease_token", sa.String(36), nullable=True))
    op.add_column("job_execucao", sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("job_execucao", "lease_expires_at")
    op.drop_column("job_execucao", "lease_token")
