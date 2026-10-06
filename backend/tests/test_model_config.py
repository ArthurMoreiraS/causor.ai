from dotenv import dotenv_values
import pytest

from app.agent.model_config import SONNET, upgrade_env


@pytest.mark.parametrize("provider,model,changed", [
    ("claude", "claude-sonnet-5", True), ("claude", "claude-sonnet-4-6", True),
    ("claude", "custom-model", False), ("openai_compat", "claude-sonnet-5", False),
])
def test_private_env_upgrade_preserves_other_settings_and_custom_choices(tmp_path, provider, model, changed):
    path = tmp_path / ".env"
    original = (f"CAUSOR_LLM_PROVIDER='{provider}'\nCAUSOR_CLAUDE_MODEL='{model}'\n"
                f"CAUSOR_CLAUDE_DRAFT_MODEL='{model}'\nOTHER_SECRET='fixture$literal'\n")
    path.write_text(original)
    result = upgrade_env(path)
    active = dotenv_values(path, interpolate=False)
    assert bool(result) is changed
    assert active["CAUSOR_CLAUDE_DRAFT_MODEL"] == (SONNET if changed else model)
    assert active["OTHER_SECRET"] == "fixture$literal"
    if changed:
        assert (tmp_path / ".env.pre-models").read_text() == original
        assert upgrade_env(path) == []
    else:
        assert path.read_text() == original
    assert not (tmp_path / ".env.models-candidate").exists()
