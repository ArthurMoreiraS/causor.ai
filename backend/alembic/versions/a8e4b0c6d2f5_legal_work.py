"""Persistent work independent of captured notices."""
from alembic import op
import sqlalchemy as sa

revision = "a8e4b0c6d2f5"
down_revision = "a7d3f9b5c1e4"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("trabalho_juridico",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("escritorio_id", sa.Integer(), sa.ForeignKey("escritorio.id"), nullable=False),
        *[sa.Column(name, sa.Integer(), sa.ForeignKey(target, ondelete="SET NULL")) for name, target in (
            ("processo_id", "processo.id"), ("intimacao_id", "intimacao.id"),
            ("prazo_id", "prazo.id"), ("peticao_id", "peticao.id"), ("responsavel_id", "usuario.id"))],
        sa.Column("providencia", sa.String(255), nullable=False),
        sa.Column("instrucoes", sa.Text(), nullable=False, server_default=""),
        sa.Column("grau", sa.String(4), nullable=False, server_default="1"),
        sa.Column("polo", sa.String(100)),
        sa.Column("versao", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("escopo", sa.JSON()), sa.Column("evidencias", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_trabalho_juridico_escritorio_id", "trabalho_juridico", ["escritorio_id"])
    op.create_index("ix_trabalho_juridico_processo_id", "trabalho_juridico", ["processo_id"])


def downgrade():
    op.drop_table("trabalho_juridico")
