"""add template_peticao

Revision ID: c2a4d9e8f013
Revises: b9f7d2c8a6e1
Create Date: 2026-06-11 17:25:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c2a4d9e8f013"
down_revision: Union[str, Sequence[str], None] = "b9f7d2c8a6e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "template_peticao",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("escritorio_id", sa.Integer(), nullable=False),
        sa.Column("tipo", sa.String(length=100), nullable=False),
        sa.Column("area", sa.String(length=100), nullable=True),
        sa.Column("nome", sa.String(length=255), nullable=False),
        sa.Column("conteudo", sa.Text(), nullable=False),
        sa.Column("ativo", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["escritorio_id"], ["escritorio.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("template_peticao")
