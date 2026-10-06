"""Upgrade known legacy Claude defaults in a private env; leave custom choices intact."""
import argparse
import json
import os
from pathlib import Path
import shutil

from dotenv import dotenv_values, set_key

SONNET = "claude-sonnet-5-5"
LEGACY = {"claude-sonnet-5", "claude-sonnet-4-6"}
KEYS = ("CAUSOR_CLAUDE_MODEL", "CAUSOR_CLAUDE_DRAFT_MODEL")


def upgrade_env(path: Path) -> list[str]:
    values = dotenv_values(path, interpolate=False)
    if values.get("CAUSOR_LLM_PROVIDER", "claude") not in ("", "claude"):
        return []
    changes = [key for key in KEYS if not values.get(key) or values[key] in LEGACY]
    if not changes:
        return []
    stat = path.stat()
    backup = path.with_name(path.name + ".pre-models")
    if not backup.exists():
        shutil.copy2(path, backup)
        backup.chmod(0o600)
        if hasattr(os, "chown"):
            os.chown(backup, stat.st_uid, stat.st_gid)
    candidate = path.with_name(path.name + ".models-candidate")
    try:
        shutil.copy2(path, candidate)
        for key in changes:
            set_key(candidate, key, SONNET)
        # dotenv replaces its inode; protect only after its last rewrite.
        candidate.chmod(0o600)
        if hasattr(os, "chown"):
            os.chown(candidate, stat.st_uid, stat.st_gid)
        os.replace(candidate, path)
    finally:
        candidate.unlink(missing_ok=True)
    return changes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--show", action="store_true")
    args = parser.parse_args()
    if args.env_file:
        changed = upgrade_env(args.env_file)
        print(json.dumps({"model_settings_upgraded": changed, "target": SONNET}))
    elif args.show:
        from app.settings import settings
        fields = ("claude_draft_model", "claude_context_model", "claude_classification_model", "claude_chat_model")
        known = LEGACY | {SONNET, "claude-haiku-4-5", "claude-haiku-4-5-20251001"}
        print(json.dumps({"configured_models": {field: getattr(settings, field) if getattr(settings, field) in known
                                               else "custom" for field in fields}}))
    else:
        parser.error("use --env-file ou --show")


if __name__ == "__main__":
    main()
