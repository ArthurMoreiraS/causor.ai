"""Migration guards and opt-in restore on disposable PostgreSQL 17.

RUN_MIGRATION_PG=1 uses a local fixture server on port 55433, not application DB.
"""

from dataclasses import dataclass
import json
import os
import uuid

import psycopg
from psycopg import sql
import pytest

from scripts import supabase_free as migration

SOURCE = "abcdefghijklmnopqrst"
TARGET = "zyxwvutsrqponmlkjihg"


def dsn(ref, port=5432, host=None):
    return f"postgresql+psycopg://postgres.{ref}:fixture@{host or 'aws-0-sa-east-1.pooler.supabase.com'}:{port}/postgres"


def configs(tmp_path, ref=TARGET, auth_ref=TARGET):
    source = tmp_path / "source.env"
    target = tmp_path / "target.env"
    source.write_text(f"CAUSOR_DATABASE_URL={dsn(SOURCE)}\n", encoding="utf-8")
    target.write_text(f"CAUSOR_TARGET_DATABASE_URL={dsn(ref)}\n"
                      f"CAUSOR_TARGET_SUPABASE_URL=https://{auth_ref}.supabase.co\n"
                      "CAUSOR_TARGET_SUPABASE_ANON_KEY=public-fixture\n", encoding="utf-8")
    return source, target


def test_configuration_check_does_not_connect(tmp_path, monkeypatch):
    monkeypatch.setattr(migration.Database, "connect", lambda _: pytest.fail("offline check"))
    origin, dest = migration.configuration(*configs(tmp_path))
    assert (origin.ref, dest.ref) == (SOURCE, TARGET)
    assert "fixture" not in repr(origin)


@pytest.mark.parametrize("value", ["", dsn(TARGET, port=6543), dsn(TARGET, host="localhost"),
                                    dsn("bad"), "sqlite:///:memory:"])
def test_invalid_connection_does_not_echo_secret(value):
    with pytest.raises(migration.MigrationError) as exc:
        migration.Database.parse(value)
    assert "fixture" not in str(exc.value)


def test_direct_database_connection():
    db = migration.Database.parse(f"postgresql://postgres:fixture@db.{TARGET}.supabase.co/postgres")
    assert db.ref == TARGET


@pytest.mark.parametrize("ref,auth_ref", [(SOURCE, SOURCE), (TARGET, SOURCE)])
def test_refuse_origin_and_mismatching_auth(tmp_path, ref, auth_ref):
    with pytest.raises(migration.MigrationError):
        migration.configuration(*configs(tmp_path, ref=ref, auth_ref=auth_ref))


def test_restore_confirmation_is_checked_before_connection(tmp_path, monkeypatch):
    _, target = migration.configuration(*configs(tmp_path))
    monkeypatch.setattr(migration.Database, "connect", lambda _: pytest.fail("must not connect"))
    for ref, origin in [(SOURCE, SOURCE), (TARGET, TARGET)]:
        with pytest.raises(migration.MigrationError):
            migration.restore(target, tmp_path, {"source_ref": origin}, ref)


def test_corrupt_backup_rejected(tmp_path):
    origin, _ = migration.configuration(*configs(tmp_path))
    (tmp_path / "manifest.json").write_text(json.dumps({
        "format": 1, "source_ref": SOURCE, "sha256": {"public.dump": "wrong"},
    }))
    (tmp_path / "public.dump").write_bytes(b"corrupt fixture")
    with pytest.raises(migration.MigrationError, match="Integridade"):
        migration.load_backup(tmp_path, origin)


def test_public_list_preserves_acl_and_audit_trigger():
    toc = "4; 2615 2200 SCHEMA - public postgres\n5; 0 0 COMMENT - SCHEMA public postgres\n"
    toc += "8; 0 2200 ACL - SCHEMA public postgres\n17; 2620 40000 TRIGGER public audit_log audit_log_append_only postgres\n"
    filtered = migration.public_restore_list(toc)
    assert "SCHEMA - public" not in filtered
    assert "COMMENT" not in filtered
    assert "ACL - SCHEMA public" in filtered
    assert "audit_log_append_only" in filtered


@dataclass(frozen=True, repr=False)
class FixtureDatabase(migration.Database):
    def connect(self):
        return psycopg.connect(host="127.0.0.1", port=55433, user="postgres",
                               password="fixture", dbname=self.name)

    def environment(self):
        return {**super().environment(), "PGHOST": "host.docker.internal", "PGPORT": "55433",
                "PGSSLMODE": "disable"}


@pytest.fixture
def fixture_databases():
    if os.environ.get("RUN_MIGRATION_PG") != "1":
        pytest.skip("opt-in disposable PostgreSQL restore")
    names = ["migration_" + uuid.uuid4().hex for _ in range(2)]
    with psycopg.connect(host="127.0.0.1", port=55433, user="postgres",
                         password="fixture", dbname="postgres", autocommit=True) as admin:
        try:
            for name in names:
                admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
            origin, target = [FixtureDatabase(ref, "host.docker.internal", "postgres", "fixture", name)
                              for ref, name in zip((SOURCE, TARGET), names, strict=True)]
            auth_schema = """
                CREATE SCHEMA auth;
                CREATE TABLE auth.schema_migrations(version text PRIMARY KEY);
                INSERT INTO auth.schema_migrations VALUES ('managed-schema-local');
                CREATE TABLE auth.users(id uuid PRIMARY KEY, encrypted_password text NOT NULL);
                CREATE TABLE auth.identities(id uuid PRIMARY KEY, user_id uuid REFERENCES auth.users(id));
            """
            for db in (origin, target):
                with db.connect() as conn:
                    conn.execute(auth_schema)
            with origin.connect() as conn:
                conn.execute("""
                    CREATE TABLE public.escritorio(id serial PRIMARY KEY, nome text NOT NULL);
                    CREATE TABLE public.audit_log(id serial PRIMARY KEY, escritorio_id integer REFERENCES public.escritorio(id), evento jsonb NOT NULL);
                    INSERT INTO public.escritorio(nome) VALUES ('Escritório fictício');
                    INSERT INTO public.audit_log(escritorio_id, evento) VALUES (1, '{"kind":"fixture"}');
                    CREATE FUNCTION public.reject_audit() RETURNS trigger LANGUAGE plpgsql AS $$
                        BEGIN RAISE EXCEPTION 'append only'; END $$;
                    CREATE TRIGGER audit_log_append_only BEFORE UPDATE OR DELETE OR TRUNCATE ON public.audit_log
                        FOR EACH STATEMENT EXECUTE FUNCTION public.reject_audit();
                    ALTER TABLE public.audit_log ENABLE ALWAYS TRIGGER audit_log_append_only;
                    INSERT INTO auth.users VALUES ('00000000-0000-0000-0000-000000000001', 'fixture-password-hash');
                    INSERT INTO auth.identities VALUES ('00000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-000000000001');
                """)
            yield origin, target
        finally:
            for name in names:
                admin.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name)))


def test_pg_backup_restore_preserves_auth_audit_and_sequence(fixture_databases, tmp_path):
    origin, target = fixture_databases
    directory = tmp_path / "backup"
    migration.backup(origin, directory, quiesced=True)
    manifest = migration.load_backup(directory, origin)
    migration.restore(target, directory, manifest, target.ref)
    migration.verify(target, manifest)
    with target.connect() as conn:
        assert conn.execute("SELECT encrypted_password FROM auth.users").fetchone()[0] == "fixture-password-hash"
        assert conn.execute("SELECT version FROM auth.schema_migrations").fetchone()[0] == "managed-schema-local"
        assert conn.execute("INSERT INTO public.escritorio(nome) VALUES ('Novo') RETURNING id").fetchone()[0] == 2
    with pytest.raises(psycopg.errors.RaiseException):
        with target.connect() as conn:
            conn.execute("DELETE FROM public.audit_log")
    with pytest.raises(migration.MigrationError, match="estruturas"):
        migration.restore(target, directory, manifest, target.ref)


def test_pg_auth_failure_rolls_back_public_schema(fixture_databases, tmp_path):
    origin, target = fixture_databases
    with target.connect() as conn:
        conn.execute("ALTER TABLE auth.users ADD COLUMN required_extra text NOT NULL")
    directory = tmp_path / "backup"
    migration.backup(origin, directory, quiesced=True)
    manifest = migration.load_backup(directory, origin)
    with pytest.raises(migration.MigrationError, match="Cliente PostgreSQL"):
        migration.restore(target, directory, manifest, target.ref)
    with target.connect() as conn:
        assert conn.execute("SELECT to_regclass('public.escritorio')").fetchone()[0] is None
        assert conn.execute("SELECT count(*) FROM auth.users").fetchone()[0] == 0
