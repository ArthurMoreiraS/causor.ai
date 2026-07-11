"""desativa sessoes de tribunal do vault (acesso migrou para o agente)

Revision ID: e2b9c3d7f6a5
Revises: d1a8b2c6e5f4
Create Date: 2026-07-10 00:00:00.000000

Migração de dados: o cofre não guarda mais sessão de tribunal (cookie).
Credenciais ``tipo='session'`` são desativadas; segredos correspondentes no
Supabase Vault são revogados pelo runbook operacional. ``cloud_cert`` fica
intacto.
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "e2b9c3d7f6a5"
down_revision: Union[str, Sequence[str], None] = "d1a8b2c6e5f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        "update credencial_assinatura set ativo = false where tipo = 'session'"
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Sem reativação automática: as sessões antigas podem ter expirado e o
    # caminho de código que as consumia foi removido.
    pass
