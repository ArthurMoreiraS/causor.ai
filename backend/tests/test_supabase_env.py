"""Test private VPS env cutover without networking or real credentials."""
import importlib.util
from pathlib import Path

from dotenv import dotenv_values
import pytest

spec = importlib.util.spec_from_file_location(
    "supabase_env", Path(__file__).resolve().parents[2] / "infra/supabase_env.py",
)
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)

SOURCE = "abcdefghijklmnopqrst"
TARGET = "zyxwvutsrqponmlkjihg"


def url(ref):
    return f"postgresql+psycopg://postgres.{ref}:fixture@aws-0-sa-east-1.pooler.supabase.com:5432/postgres"


@pytest.fixture
def envs(tmp_path):
    current = tmp_path / ".env"
    original = f"CAUSOR_DATABASE_URL='{url(SOURCE)}'\nCAUSOR_SUPABASE_JWT_SECRET='old-fixture'\nKEEP_LITERAL='dollar$sign'\n"
    current.write_text(original)
    values = {"CAUSOR_MIGRATION_DATABASE_URL": url(TARGET),
              "CAUSOR_MIGRATION_SUPABASE_URL": f"https://{TARGET}.supabase.co"}
    return tmp_path, original, values


def test_cutover_preserves_original_and_clears_old_signing_secret(envs):
    directory, original, values = envs
    helper.configure(directory, SOURCE, TARGET, values)
    assert (directory / ".env.pre-supabase").read_text() == original
    active = dotenv_values(directory / ".env", interpolate=False)
    assert active["CAUSOR_DATABASE_URL"] == url(TARGET)
    assert active["CAUSOR_SUPABASE_JWT_SECRET"] == ""
    assert active["KEEP_LITERAL"] == "dollar$sign"
    helper.rollback(directory, SOURCE, TARGET)
    assert (directory / ".env").read_text() == original
    assert not (directory / ".env.supabase-candidate").exists()


@pytest.mark.parametrize("change", ["origin", "destination", "auth", "rollback"])
def test_mismatch_never_replaces_env(envs, change):
    directory, original, values = envs
    source = SOURCE
    if change == "origin":
        source = TARGET
    elif change == "destination":
        values["CAUSOR_MIGRATION_DATABASE_URL"] = url(SOURCE)
    elif change == "auth":
        values["CAUSOR_MIGRATION_SUPABASE_URL"] = f"https://{SOURCE}.supabase.co"
    else:
        (directory / ".env.pre-supabase").write_text("other-rollback")
    with pytest.raises(ValueError):
        helper.configure(directory, source, TARGET, values)
    assert (directory / ".env").read_text() == original


def test_rollback_refuses_foreign_project(envs):
    directory, original, values = envs
    helper.configure(directory, SOURCE, TARGET, values)
    before = (directory / ".env").read_bytes()
    with pytest.raises(ValueError):
        helper.rollback(directory, TARGET, SOURCE)
    assert (directory / ".env").read_bytes() == before
