"""add escritorio timbrado

Revision ID: f0a1b2c3d4e5
Revises: e9a3c1f52b8d
Create Date: 2026-07-09 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f0a1b2c3d4e5"
down_revision: Union[str, Sequence[str], None] = "e9a3c1f52b8d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("escritorio", sa.Column("timbrado_logo", sa.LargeBinary(), nullable=True))
    op.add_column(
        "escritorio", sa.Column("timbrado_logo_mime", sa.String(length=30), nullable=True)
    )
    op.add_column("escritorio", sa.Column("timbrado_cabecalho", sa.Text(), nullable=True))
    op.add_column("escritorio", sa.Column("timbrado_rodape", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("escritorio", "timbrado_rodape")
    op.drop_column("escritorio", "timbrado_cabecalho")
    op.drop_column("escritorio", "timbrado_logo_mime")
    op.drop_column("escritorio", "timbrado_logo")
