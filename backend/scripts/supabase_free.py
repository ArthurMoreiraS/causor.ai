"""Offline configuration check and guarded logical Supabase migration.

Run from backend with the existing venv. No command changes application envs.
Database credentials are read from ignored files, never passed in argv/logs.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

from dotenv import dotenv_values
import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
FILES = ("public.dump", "auth-data.sql")
IMAGE = "postgres:17"


class MigrationError(Exception):
    """Messages must contain neither connection strings nor row values."""


@dataclass(frozen=True, repr=False)
class Database:
    ref: str
    host: str
    user: str
    password: str
    name: str

    @classmethod
    def parse(cls, value: str) -> Database:
        try:
            url = make_url(value)
            host = url.host or ""
            user = url.username or ""
            if host.endswith(".pooler.supabase.com"):
                ref = user.rsplit(".", 1)[-1]
            elif host.startswith("db.") and host.endswith(".supabase.co"):
                ref = host[3:-12]
            else:
                raise ValueError
            if (url.get_backend_name() != "postgresql" or url.port not in (None, 5432)
                    or not re.fullmatch(r"[a-z0-9]{20}", ref)
                    or not url.password or not url.database):
                raise ValueError
            return cls(ref, host, user, url.password, url.database)
        except Exception:
            raise MigrationError("Conexão inválida: use Direct ou Session pooler na porta 5432.") from None

    def connect(self):
        return psycopg.connect(
            host=self.host, port=5432, user=self.user, password=self.password,
            dbname=self.name, sslmode="require", connect_timeout=15,
        )

    def environment(self) -> dict[str, str]:
        return {"PGHOST": self.host, "PGPORT": "5432", "PGUSER": self.user,
                "PGPASSWORD": self.password, "PGDATABASE": self.name, "PGSSLMODE": "require"}


def configuration(source_file: Path, target_file: Path) -> tuple[Database, Database]:
    source = dotenv_values(source_file, interpolate=False)
    target = dotenv_values(target_file, interpolate=False)
    origin = Database.parse(source.get("CAUSOR_DATABASE_URL") or "")
    dest = Database.parse(target.get("CAUSOR_TARGET_DATABASE_URL") or "")
    if origin.ref == dest.ref:
        raise MigrationError("Destino é o projeto de origem; operação recusada.")
    if (target.get("CAUSOR_TARGET_SUPABASE_URL") or "").rstrip("/") != f"https://{dest.ref}.supabase.co":
        raise MigrationError("URL de Auth não corresponde ao projeto do banco de destino.")
    if not target.get("CAUSOR_TARGET_SUPABASE_ANON_KEY"):
        raise MigrationError("Falta a chave pública do destino.")
    return origin, dest


def client(db: Database, directory: Path, *args: str, read_only: bool = False) -> str:
    """Official PostgreSQL clients in a disposable container; stderr stays private."""
    env = {**os.environ, **db.environment()}
    mount = f"type=bind,src={directory.resolve()},dst=/backup"
    if read_only:
        mount += ",readonly"
    cmd = ["docker", "run", "--rm", "--mount", mount]
    for key in db.environment():
        cmd += ["--env", key]  # Docker reads values from the child environment.
    result = subprocess.run(cmd + [IMAGE, *args], env=env, capture_output=True, timeout=600)
    if result.returncode:
        raise MigrationError("Cliente PostgreSQL falhou; nenhuma configuração de produção foi alterada.")
    return result.stdout.decode("utf-8")


def start_read_only(conn):
    conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
    conn.execute("SET LOCAL timezone = 'UTC'")
    conn.execute("SET LOCAL datestyle = 'ISO, YMD'")


def table_columns(conn, schema: str, table: str) -> list[list[str]]:
    return [list(row) for row in conn.execute("""
        SELECT a.attname, format_type(a.atttypid, a.atttypmod)
        FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid
        JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname=%s AND c.relname=%s AND a.attnum>0 AND NOT a.attisdropped
        ORDER BY a.attnum
    """, (schema, table))]


def fingerprint(conn, schema: str, table: str, columns: list[list[str]]) -> list:
    names = sql.SQL(", ").join(sql.Identifier(col[0]) for col in columns)
    query = sql.SQL("""
        SELECT count(*), md5(coalesce(string_agg(h, '' ORDER BY h), ''))
        FROM (SELECT md5(to_jsonb(r)::text) h FROM
            (SELECT {} FROM {}.{}) r) hashes
    """).format(names, sql.Identifier(schema), sql.Identifier(table))
    return list(conn.execute(query).fetchone())


def inventory(conn) -> dict:
    tables = {}
    for schema, table in conn.execute("""
        SELECT n.nspname, c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname IN ('public', 'auth') AND c.relkind IN ('r', 'p')
          AND NOT (n.nspname='auth' AND c.relname='schema_migrations')
          AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.objid=c.oid
                          AND d.classid='pg_class'::regclass AND d.deptype='e')
        ORDER BY 1,2
    """):
        columns = table_columns(conn, schema, table)
        tables[f"{schema}.{table}"] = {
            "columns": columns, "fingerprint": fingerprint(conn, schema, table, columns),
        }
    sequences = {}
    for (name,) in conn.execute("SELECT sequencename FROM pg_sequences WHERE schemaname='public'"):
        query = sql.SQL("SELECT last_value, is_called FROM public.{}").format(sql.Identifier(name))
        sequences[name] = list(conn.execute(query).fetchone())
    return {"tables": tables, "sequences": sequences}


def supported_source(conn):
    major = int(conn.execute("SHOW server_version_num").fetchone()[0]) // 10000
    if major != 17:
        raise MigrationError("Este procedimento exige PostgreSQL 17; revisar versão antes de continuar.")
    for table in ("vault.secrets", "storage.objects", "storage.buckets"):
        if conn.execute("SELECT to_regclass(%s)", (table,)).fetchone()[0]:
            schema, name = table.split(".")
            count = conn.execute(sql.SQL("SELECT count(*) FROM {}.{}").format(
                sql.Identifier(schema), sql.Identifier(name))).fetchone()[0]
            if count:
                raise MigrationError("Vault/Storage não está vazio; exige migração específica antes de continuar.")
    custom_triggers = conn.execute("""
        SELECT count(*) FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid
        JOIN pg_namespace n ON n.oid=c.relnamespace JOIN pg_proc p ON p.oid=t.tgfoid
        JOIN pg_namespace pn ON pn.oid=p.pronamespace
        WHERE n.nspname IN ('auth','storage') AND NOT t.tgisinternal
          AND pn.nspname NOT IN ('auth','storage')
    """).fetchone()[0]
    if custom_triggers:
        raise MigrationError("Há triggers personalizados em Auth/Storage; revisar sua migração separadamente.")


def backup(origin: Database, directory: Path, quiesced: bool):
    if not quiesced:
        raise MigrationError("Pause os consumidores e o acesso de escrita antes do backup final.")
    directory.mkdir(parents=True, exist_ok=False)
    with origin.connect() as conn:
        start_read_only(conn)
        supported_source(conn)
        snapshot = conn.execute("SELECT pg_export_snapshot()").fetchone()[0]
        manifest = {"format": 1, "source_ref": origin.ref, "postgres_major": 17, **inventory(conn)}
        client(origin, directory, "pg_dump", "--format=custom", "--schema=public", "--no-owner",
               f"--snapshot={snapshot}", "--file=/backup/public.dump")
        client(origin, directory, "pg_dump", "--data-only", "--schema=auth", "--no-owner", "--no-acl",
               "--exclude-table=auth.schema_migrations", f"--snapshot={snapshot}",
               "--file=/backup/auth-data.sql")
    manifest["sha256"] = {}
    for name in FILES:
        with (directory / name).open("rb") as stream:
            manifest["sha256"][name] = hashlib.file_digest(stream, "sha256").hexdigest()
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def load_backup(directory: Path, origin: Database) -> dict:
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("format") != 1 or manifest.get("source_ref") != origin.ref:
        raise MigrationError("Backup não pertence à origem configurada.")
    for name in FILES:
        with (directory / name).open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if digest != manifest.get("sha256", {}).get(name):
            raise MigrationError("Integridade do backup inválida; restauração recusada.")
    return manifest


def pristine_target(conn, manifest: dict):
    major = int(conn.execute("SHOW server_version_num").fetchone()[0]) // 10000
    if major != manifest["postgres_major"]:
        raise MigrationError("Versão PostgreSQL do destino difere do backup.")
    relations = conn.execute("""
        SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='public' AND c.relkind IN ('r','p','v','m','S','f')
          AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.objid=c.oid
                          AND d.classid='pg_class'::regclass AND d.deptype='e')
    """).fetchone()[0]
    if relations:
        raise MigrationError("Destino contém estruturas de aplicação; restauração recusada.")
    for key, data in manifest["tables"].items():
        schema, table = key.split(".")
        if schema != "auth":
            continue
        columns = table_columns(conn, schema, table)
        if not all(col in columns for col in data["columns"]):
            raise MigrationError("Schema Auth do destino incompatível; revisar antes de restaurar.")
        if fingerprint(conn, schema, table, data["columns"])[0]:
            raise MigrationError("Destino contém dados Auth; restauração recusada.")


def public_restore_list(toc: str) -> str:
    # Supabase already has public. Preserve grants/functions/triggers/RLS;
    # omit only creation/comment for that existing namespace, never drop it.
    return "\n".join(line for line in toc.splitlines()
                     if not re.match(r"^\d+; \d+ \d+ (SCHEMA - public |COMMENT - SCHEMA public )", line)) + "\n"


def restore(dest: Database, directory: Path, manifest: dict, confirmed_ref: str):
    if confirmed_ref != dest.ref or dest.ref == manifest["source_ref"]:
        raise MigrationError("Identificador do destino não confirmado ou igual à origem.")
    with dest.connect() as conn:
        start_read_only(conn)
        pristine_target(conn, manifest)
    toc = client(dest, directory, "pg_restore", "--list", "/backup/public.dump", read_only=True)
    (directory / "public.list").write_text(public_restore_list(toc), encoding="utf-8")
    client(dest, directory, "pg_restore", "--no-owner", "--use-list=/backup/public.list",
           "--file=/backup/public.sql", "/backup/public.dump")
    client(dest, directory, "psql", "--no-psqlrc", "--single-transaction", "--set=ON_ERROR_STOP=1",
           "--command=SET timezone='UTC'", "--file=/backup/public.sql",
           "--command=SET session_replication_role=replica", "--file=/backup/auth-data.sql",
           read_only=True)
    verify(dest, manifest)


def verify(dest: Database, manifest: dict):
    with dest.connect() as conn:
        start_read_only(conn)
        for key, data in manifest["tables"].items():
            schema, table = key.split(".")
            if fingerprint(conn, schema, table, data["columns"]) != data["fingerprint"]:
                raise MigrationError("Conteúdo restaurado difere do backup; não trocar produção.")
        for name, expected in manifest["sequences"].items():
            query = sql.SQL("SELECT last_value, is_called FROM public.{}").format(sql.Identifier(name))
            if list(conn.execute(query).fetchone()) != expected:
                raise MigrationError("Sequência restaurada difere do backup; não trocar produção.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check", "backup", "restore", "verify"))
    parser.add_argument("--source-env", type=Path, default=ROOT / ".env")
    parser.add_argument("--target-env", type=Path, default=ROOT / "artifacts/supabase-free/destino.env")
    parser.add_argument("--backup-dir", type=Path)
    parser.add_argument("--source-quiesced", action="store_true")
    parser.add_argument("--confirm-target", default="")
    args = parser.parse_args()
    try:
        origin, dest = configuration(args.source_env, args.target_env)
        if args.command == "check":
            print("Configuração válida; nenhuma conexão, escrita ou troca de produção executada.")
            return 0
        if args.backup_dir is None:
            raise MigrationError("Informe --backup-dir dentro de backend/artifacts/supabase-free.")
        directory = args.backup_dir.resolve()
        if not directory.is_relative_to((ROOT / "artifacts/supabase-free").resolve()):
            raise MigrationError("Diretório deve ficar no local privado ignorado pelo Git.")
        if args.command == "backup":
            backup(origin, directory, args.source_quiesced)
        else:
            manifest = load_backup(directory, origin)
            if args.command == "restore":
                restore(dest, directory, manifest, args.confirm_target)
            else:
                verify(dest, manifest)
        print("Operação concluída; configuração de produção permanece sem alteração.")
        return 0
    except MigrationError as exc:
        print(str(exc))
    except Exception as exc:
        # Database errors can include passwords, emails and failed COPY rows.
        print(f"Operação interrompida ({type(exc).__name__}); detalhes privados não exibidos.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
