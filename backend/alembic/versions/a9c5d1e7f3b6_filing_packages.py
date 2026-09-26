"""Versioned filing packages, attempts and private receipt evidence."""
from alembic import op
import sqlalchemy as sa

revision = "a9c5d1e7f3b6"
down_revision = "a8e4b0c6d2f5"
branch_labels = None
depends_on = None


def timestamps():
    return [sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False)]


def upgrade():
    op.create_table("pacote_protocolo",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("escritorio_id", sa.Integer(), sa.ForeignKey("escritorio.id"), nullable=False),
        sa.Column("trabalho_id", sa.Integer(), sa.ForeignKey("trabalho_juridico.id", ondelete="SET NULL")),
        sa.Column("peticao_id", sa.Integer(), sa.ForeignKey("peticao.id", ondelete="SET NULL")),
        sa.Column("versao", sa.Integer(), nullable=False), sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("dados", sa.JSON(), nullable=False),
        sa.Column("aprovada_por", sa.Integer(), sa.ForeignKey("usuario.id", ondelete="SET NULL")),
        sa.Column("aprovada_em", sa.DateTime(timezone=True)), *timestamps(),
        sa.UniqueConstraint("trabalho_id", "versao", name="uq_pacote_trabalho_versao"))
    op.create_table("tentativa_protocolo",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("escritorio_id", sa.Integer(), sa.ForeignKey("escritorio.id"), nullable=False),
        sa.Column("pacote_id", sa.Integer(), sa.ForeignKey("pacote_protocolo.id"), nullable=False),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("canal", sa.String(30), nullable=False), sa.Column("status", sa.String(40), nullable=False),
        sa.Column("versao", sa.Integer(), nullable=False), sa.Column("dados", sa.JSON()), *timestamps(),
        sa.UniqueConstraint("escritorio_id", "idempotency_key", name="uq_tentativa_key"))
    op.create_table("comprovante_protocolo",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("escritorio_id", sa.Integer(), sa.ForeignKey("escritorio.id"), nullable=False),
        sa.Column("tentativa_id", sa.Integer(), sa.ForeignKey("tentativa_protocolo.id"), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False), sa.Column("storage_key", sa.String(1024), nullable=False),
        sa.Column("nome", sa.String(255), nullable=False), sa.Column("status", sa.String(40), nullable=False),
        sa.Column("dados", sa.JSON()), *timestamps())
    for table, columns in (("pacote_protocolo", ("escritorio_id", "trabalho_id")),
                           ("tentativa_protocolo", ("escritorio_id", "pacote_id")),
                           ("comprovante_protocolo", ("escritorio_id", "tentativa_id"))):
        for column in columns:
            op.create_index(f"ix_{table}_{column}", table, [column])


def downgrade():
    op.drop_table("comprovante_protocolo")
    op.drop_table("tentativa_protocolo")
    op.drop_table("pacote_protocolo")
