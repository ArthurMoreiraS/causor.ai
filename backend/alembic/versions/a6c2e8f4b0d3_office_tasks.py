"""Office tasks linked to clients and legal work.

Revision ID: a6c2e8f4b0d3
Revises: a5f1b7d3c9e2
"""
from alembic import op
import sqlalchemy as sa

revision = "a6c2e8f4b0d3"
down_revision = "a5f1b7d3c9e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tarefa",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("escritorio_id", sa.Integer(), sa.ForeignKey("escritorio.id"), nullable=False),
        sa.Column("titulo", sa.String(255), nullable=False),
        sa.Column("descricao", sa.Text()),
        sa.Column("tipo", sa.String(30), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("prioridade", sa.String(20), nullable=False),
        sa.Column("data_prevista", sa.Date()),
        *[sa.Column(column, sa.Integer(), sa.ForeignKey(f"{table}.id", ondelete="SET NULL"))
          for column, table in (("processo_id", "processo"), ("cliente_id", "cliente"),
                                ("intimacao_id", "intimacao"), ("peticao_id", "peticao"), ("responsavel_id", "usuario"))],
        sa.Column("origem", sa.String(30), nullable=False),
        sa.Column("origem_key", sa.String(64)),
        sa.Column("origem_texto", sa.Text()),
        sa.Column("versao", sa.Integer(), nullable=False),
        sa.Column("concluida_em", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("escritorio_id", "origem_key", name="uq_tarefa_origem"),
    )
    op.create_index("ix_tarefa_escritorio_id", "tarefa", ["escritorio_id"])
    op.create_index("ix_tarefa_processo_id", "tarefa", ["processo_id"])


def downgrade() -> None:
    op.drop_table("tarefa")
