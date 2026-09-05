"""Block mutation of audit events at the PostgreSQL boundary.

Revision ID: a4d9e2c7b6f1
Revises: a3e7b1c9d2f8
"""

from alembic import op

revision = "a4d9e2c7b6f1"
down_revision = "a3e7b1c9d2f8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE FUNCTION causor_reject_audit_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'audit_log is append-only' USING ERRCODE = '42501';
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER audit_log_append_only
        BEFORE UPDATE OR DELETE OR TRUNCATE ON audit_log
        FOR EACH STATEMENT EXECUTE FUNCTION causor_reject_audit_mutation()
    """)
    op.execute("ALTER TABLE audit_log ENABLE ALWAYS TRIGGER audit_log_append_only")


def downgrade() -> None:
    op.execute("DROP TRIGGER audit_log_append_only ON audit_log")
    op.execute("DROP FUNCTION causor_reject_audit_mutation()")
