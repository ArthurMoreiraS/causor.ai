"""estado derivado de sessao de tribunal por rota

Revision ID: d1a8b2c6e5f4
Revises: c8e6f0a4b3d2
Create Date: 2026-07-10 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d1a8b2c6e5f4"
down_revision: Union[str, Sequence[str], None] = "c8e6f0a4b3d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "court_session_state",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "escritorio_id",
            sa.Integer(),
            sa.ForeignKey("escritorio.id"),
            nullable=False,
        ),
        sa.Column(
            "installation_id",
            sa.Integer(),
            sa.ForeignKey("agent_installation.id"),
            nullable=True,
        ),
        sa.Column("sistema", sa.String(length=20), nullable=False),
        sa.Column("tribunal", sa.String(length=50), nullable=False),
        sa.Column("grau", sa.String(length=4), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="desconectado",
        ),
        sa.Column("version_marker", sa.String(length=80), nullable=True),
        sa.Column("last_confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "escritorio_id", "sistema", "tribunal", "grau",
            name="uq_court_session_route",
        ),
    )
    op.create_index(
        "ix_court_session_state_escritorio_id",
        "court_session_state",
        ["escritorio_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_court_session_state_escritorio_id", table_name="court_session_state"
    )
    op.drop_table("court_session_state")
