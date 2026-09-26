"""Page extraction checkpoints and work-linked tasks; legacy rows remain nullable."""
from alembic import op
import sqlalchemy as sa

revision = "b0d6e2f8a4c7"
down_revision = "a9c5d1e7f3b6"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("documento_arquivo", sa.Column("extraction_pages", sa.JSON(), nullable=True))
    op.add_column("tarefa", sa.Column("trabalho_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_tarefa_trabalho", "tarefa", "trabalho_juridico", ["trabalho_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_tarefa_trabalho_id", "tarefa", ["trabalho_id"])


def downgrade():
    op.drop_index("ix_tarefa_trabalho_id", "tarefa")
    op.drop_constraint("fk_tarefa_trabalho", "tarefa", type_="foreignkey")
    op.drop_column("tarefa", "trabalho_id")
    op.drop_column("documento_arquivo", "extraction_pages")
