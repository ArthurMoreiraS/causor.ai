"""backfill tenant escritorio_id on null rows

Re-applies the tenant backfill from e4c2a1f09d31. That migration backfilled
once, at upgrade time; demo seed runs that happened *after* it (with buggy code
that did not stamp escritorio_id) left intimacao/prazo/peticao rows with NULL
tenant — invisible to tenant_select() after login. This idempotent migration
re-derives escritorio_id from the owning processo for any row still NULL, so a
re-upgrade fixes existing databases without depending on a re-seed.

Safe to run repeatedly and on already-correct databases (no-op when nothing is
NULL). Rows whose processo_id is NULL cannot be derived and are left untouched.

Revision ID: f5d8e3a2b1c4
Revises: e4c2a1f09d31
Create Date: 2026-06-17
"""
from collections.abc import Sequence
from typing import Union

from alembic import op

revision: str = "f5d8e3a2b1c4"
down_revision: Union[str, Sequence[str], None] = "e4c2a1f09d31"
branch_labels = None
depends_on = None


_TABELAS = ("prazo", "peticao", "intimacao")


def upgrade() -> None:
    for tabela in _TABELAS:
        op.execute(
            f"UPDATE {tabela} SET escritorio_id = ("
            "SELECT p.escritorio_id FROM processo p WHERE p.id = "
            f"{tabela}.processo_id"
            ") WHERE escritorio_id IS NULL AND processo_id IS NOT NULL"
        )


def downgrade() -> None:
    # Backfill is not reversible: we cannot tell which rows were NULL before.
    pass
