"""validacao live persistida de conectores

Revision ID: c9f7a1b5d4e3
Revises: e2b9c3d7f6a5
Create Date: 2026-07-10 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c9f7a1b5d4e3"
down_revision: Union[str, Sequence[str], None] = "e2b9c3d7f6a5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "connector_validation",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "escritorio_id", sa.Integer(), sa.ForeignKey("escritorio.id"), nullable=False
        ),
        sa.Column(
            "installation_id",
            sa.Integer(),
            sa.ForeignKey("agent_installation.id"),
            nullable=False,
        ),
        sa.Column("profile_key", sa.String(length=160), nullable=False),
        sa.Column("capability", sa.String(length=50), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("documents_count", sa.Integer(), nullable=True),
        sa.Column("manifest_fingerprint", sa.String(length=71), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("evidence", sa.JSON(), nullable=True),
        sa.Column("agent_version", sa.String(length=40), nullable=True),
        sa.Column("app_revision", sa.String(length=64), nullable=False),
        sa.Column("tested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_connector_validation_escritorio_id",
        "connector_validation",
        ["escritorio_id"],
    )
    op.create_index(
        "ix_connector_validation_profile_key",
        "connector_validation",
        ["profile_key"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_connector_validation_profile_key", table_name="connector_validation"
    )
    op.drop_index(
        "ix_connector_validation_escritorio_id", table_name="connector_validation"
    )
    op.drop_table("connector_validation")
