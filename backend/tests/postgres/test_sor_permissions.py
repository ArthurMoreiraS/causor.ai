"""Block bypass of tenant-scoped FastAPI using the public Supabase roles."""
from sqlalchemy import text

from app.sor.permissions import LOCKDOWN_SQL


def test_sor_and_future_tables_not_readable_by_public_roles(pg_engine):
    with pg_engine.begin() as conn:
        schema = conn.scalar(text("SELECT current_schema()"))
        for role in ("anon", "authenticated"):
            exists = conn.scalar(text("SELECT count(*) FROM pg_roles WHERE rolname=:role"), {"role": role})
            if not exists:
                conn.execute(text(f'CREATE ROLE "{role}" NOLOGIN'))
        # Reproduce Supabase's original broad default ACL.
        conn.execute(text(f'GRANT SELECT ON ALL TABLES IN SCHEMA "{schema}" TO anon, authenticated, PUBLIC'))
        conn.execute(text(f'GRANT USAGE ON ALL SEQUENCES IN SCHEMA "{schema}" TO anon, authenticated, PUBLIC'))
        conn.execute(text(f'ALTER DEFAULT PRIVILEGES IN SCHEMA "{schema}" GRANT SELECT ON TABLES TO anon, authenticated, PUBLIC'))
        conn.execute(text(LOCKDOWN_SQL))
        conn.execute(text("CREATE TABLE permission_future_table(id serial PRIMARY KEY)"))
        for role in ("anon", "authenticated"):
            readable = conn.scalar(text("""
                SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                WHERE n.nspname=:schema AND c.relkind='r'
                  AND has_table_privilege(:role,c.oid,'SELECT')
            """), {"schema": schema, "role": role})
            assert readable == 0
            assert not conn.scalar(text(
                "SELECT has_sequence_privilege(:role, 'permission_future_table_id_seq', 'USAGE')",
            ), {"role": role})
        # Backend role retains normal SOR CRUD and sequence access.
        assert conn.scalar(text("INSERT INTO permission_future_table DEFAULT VALUES RETURNING id")) == 1
        assert conn.scalar(text("SELECT count(*) FROM escritorio")) == 0
