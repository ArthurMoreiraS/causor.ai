"""indice FTS portugues em documento_trecho

Revision ID: c8e6f0a4b3d2
Revises: b7d5e9f3a2c1
Create Date: 2026-07-10 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c8e6f0a4b3d2"
down_revision: Union[str, Sequence[str], None] = "b7d5e9f3a2c1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        "create index if not exists ix_documento_trecho_fts "
        "on documento_trecho using gin (to_tsvector('portuguese', texto))"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("drop index if exists ix_documento_trecho_fts")
