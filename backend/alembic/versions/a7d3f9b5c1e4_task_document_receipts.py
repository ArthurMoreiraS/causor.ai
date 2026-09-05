"""Link task receipts to immutable document versions."""
from alembic import op
import sqlalchemy as sa

revision = "a7d3f9b5c1e4"
down_revision = "a6c2e8f4b0d3"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("tarefa_documento",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("escritorio_id", sa.Integer(), sa.ForeignKey("escritorio.id"), nullable=False),
        sa.Column("tarefa_id", sa.Integer(), sa.ForeignKey("tarefa.id", ondelete="CASCADE"), nullable=False),
        sa.Column("documento_id", sa.Integer(), sa.ForeignKey("documento.id", ondelete="SET NULL")),
        sa.Column("documento_arquivo_id", sa.Integer(), sa.ForeignKey("documento_arquivo.id", ondelete="SET NULL")),
        sa.Column("nome", sa.String(255), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tarefa_id", "documento_arquivo_id", name="uq_tarefa_documento_versao"))
    op.create_index("ix_tarefa_documento_escritorio_id", "tarefa_documento", ["escritorio_id"])
    op.create_index("ix_tarefa_documento_tarefa_id", "tarefa_documento", ["tarefa_id"])


def downgrade():
    op.drop_table("tarefa_documento")
