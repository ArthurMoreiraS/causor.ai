"""add sistema/grau/tipo to credencial_assinatura + backfill

Generaliza a credencial de "PJeSession" para um chaveiro multi-tribunal: cada
sessao carrega ``sistema`` (PJe/e-SAJ/EPROC/Projudi) e ``grau`` (1/2), e ``tipo``
distingue sessao de navegacao (``session``) de referencia de assinatura
(``cloud_cert``). Backfill: sessoes PJe antigas viram ``CourtSession``/``session``
/``sistema=PJe``; referencias de assinatura viram ``cloud_cert``.

Revision ID: e9a3c1f52b8d
Revises: d8f2b1e6c4a7
Create Date: 2026-07-07 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "e9a3c1f52b8d"
down_revision: Union[str, Sequence[str], None] = "d8f2b1e6c4a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("credencial_assinatura") as batch_op:
        batch_op.add_column(sa.Column("sistema", sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column("grau", sa.String(length=4), nullable=True))
        batch_op.add_column(
            sa.Column(
                "tipo",
                sa.String(length=20),
                nullable=False,
                server_default="session",
            )
        )
    # Backfill: sessoes PJe antigas -> CourtSession/session/PJe.
    op.execute(
        "update credencial_assinatura set provedor='CourtSession', "
        "sistema='PJe', grau='1', tipo='session' where provedor='PJeSession'"
    )
    # Backfill: referencias de assinatura (birdid/vidaas/a1/...) -> cloud_cert.
    op.execute(
        "update credencial_assinatura set tipo='cloud_cert' "
        "where provedor <> 'CourtSession'"
    )


def downgrade() -> None:
    with op.batch_alter_table("credencial_assinatura") as batch_op:
        batch_op.drop_column("tipo")
        batch_op.drop_column("grau")
        batch_op.drop_column("sistema")
