"""Run in the trusted backend image with /opt/causor mounted at /deploy.

Only edits private env files. Never logs values; origin stays available.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil

from dotenv import dotenv_values, set_key
from sqlalchemy.engine import make_url


def project_ref(dsn):
    url = make_url(dsn)
    if (url.host or "").endswith(".pooler.supabase.com"):
        return (url.username or "").rsplit(".", 1)[-1]
    if (url.host or "").startswith("db.") and url.host.endswith(".supabase.co"):
        return url.host[3:-12]
    raise ValueError("Unsupported database host")


def protect(path, previous_stat):
    path.chmod(0o600)
    if hasattr(os, "chown"):
        os.chown(path, previous_stat.st_uid, previous_stat.st_gid)


def configure(directory: Path, source_ref: str, target_ref: str, values: dict):
    current = directory / ".env"
    backup = directory / ".env.pre-supabase"
    candidate = directory / ".env.supabase-candidate"
    current_values = dotenv_values(current, interpolate=False)
    if project_ref(current_values.get("CAUSOR_DATABASE_URL") or "") != source_ref:
        raise ValueError("Current project differs from expected origin")
    if source_ref == target_ref or project_ref(values["CAUSOR_MIGRATION_DATABASE_URL"]) != target_ref:
        raise ValueError("Invalid destination")
    if values["CAUSOR_MIGRATION_SUPABASE_URL"].rstrip("/") != f"https://{target_ref}.supabase.co":
        raise ValueError("Auth and database differ")
    if backup.exists():
        # Never overwrite a different rollback point.
        if backup.read_bytes() != current.read_bytes():
            raise ValueError("Rollback configuration differs from current origin")
    else:
        shutil.copy2(current, backup)
        protect(backup, current.stat())
    try:
        shutil.copy2(current, candidate)
        protect(candidate, current.stat())
        set_key(candidate, "CAUSOR_DATABASE_URL", values["CAUSOR_MIGRATION_DATABASE_URL"])
        set_key(candidate, "CAUSOR_SUPABASE_URL", values["CAUSOR_MIGRATION_SUPABASE_URL"])
        # ES256/JWKS must not continue accepting the old project's HS256 key.
        set_key(candidate, "CAUSOR_SUPABASE_JWT_SECRET", values.get("CAUSOR_MIGRATION_JWT_SECRET", ""))
        os.replace(candidate, current)
    finally:
        candidate.unlink(missing_ok=True)


def rollback(directory: Path, source_ref: str, target_ref: str):
    current = directory / ".env"
    backup = directory / ".env.pre-supabase"
    candidate = directory / ".env.supabase-candidate"
    old = dotenv_values(backup, interpolate=False)
    active = dotenv_values(current, interpolate=False)
    if project_ref(old.get("CAUSOR_DATABASE_URL") or "") != source_ref:
        raise ValueError("Rollback project differs from origin")
    if project_ref(active.get("CAUSOR_DATABASE_URL") or "") not in (source_ref, target_ref):
        raise ValueError("Current project not part of this migration")
    try:
        shutil.copy2(backup, candidate)
        protect(candidate, current.stat())
        os.replace(candidate, current)
    finally:
        candidate.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("configure", "rollback"))
    parser.add_argument("source_ref")
    parser.add_argument("target_ref")
    args = parser.parse_args()
    try:
        directory = Path(os.environ.get("CAUSOR_DEPLOY_DIR", "/deploy"))
        if args.action == "configure":
            configure(directory, args.source_ref, args.target_ref, dict(os.environ))
        else:
            rollback(directory, args.source_ref, args.target_ref)
        print("Private configuration updated; no database data modified.")
    except Exception as exc:
        print(f"Configuration update refused ({type(exc).__name__}); values not displayed.")
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
