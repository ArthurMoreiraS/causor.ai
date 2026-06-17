"""TDD for the pluggable LLM provider seam (app/agent/llm.py).

No real network. We inject fake SDK clients and assert how each provider invokes
its SDK and maps the response. The factory selects the provider by config so
swapping models later is an env-var change, never a caller change.
"""

import json
from types import SimpleNamespace

import pytest
from pydantic import BaseModel, Field

from app.agent import llm


class _Schema(BaseModel):
    rotulo: str
    confianca: float = Field(ge=0.0, le=1.0)


# ---- factory -----------------------------------------------------------------


def test_get_provider_defaults_to_gemini():
    provider = llm.get_provider()
    assert isinstance(provider, llm.GeminiProvider)


def test_get_provider_returns_claude_when_named():
    provider = llm.get_provider("claude")
    assert isinstance(provider, llm.ClaudeProvider)


def test_get_provider_rejects_unknown():
    with pytest.raises(ValueError, match="desconhecido"):
        llm.get_provider("gpt-9000")


# ---- GeminiProvider ----------------------------------------------------------


def _fake_genai_client(text: str) -> SimpleNamespace:
    response = SimpleNamespace(text=text)
    models = SimpleNamespace(generate_content=lambda **kwargs: response)
    client = SimpleNamespace(models=models, _last=None)

    def _capture(**kwargs):
        client._last = kwargs
        return response

    models.generate_content = _capture
    return client


def test_gemini_complete_structured_parses_json():
    client = _fake_genai_client(json.dumps({"rotulo": "Contestação", "confianca": 0.8}))
    provider = llm.GeminiProvider(client=client, model="gemini-2.5-flash")

    result = provider.complete_structured(system="sys", user="classifique", schema=_Schema)

    assert isinstance(result, _Schema)
    assert result.rotulo == "Contestação"
    assert result.confianca == 0.8
    # JSON mode + schema requested; system goes via system_instruction.
    cfg = client._last["config"]
    assert cfg["response_mime_type"] == "application/json"
    assert cfg["system_instruction"] == "sys"


def test_gemini_complete_structured_clamps_out_of_range_floats():
    """Gemini ignores ge/le in the schema; values must be clamped before pydantic."""
    client = _fake_genai_client(json.dumps({"rotulo": "x", "confianca": 1.7}))
    provider = llm.GeminiProvider(client=client, model="gemini-2.5-flash")

    result = provider.complete_structured(system="s", user="u", schema=_Schema)

    assert result.confianca == 1.0


def test_gemini_complete_text_returns_text():
    client = _fake_genai_client("EXCELENTÍSSIMO... CONTESTAÇÃO")
    provider = llm.GeminiProvider(client=client, model="gemini-2.5-flash")

    out = provider.complete_text(system="sys", user="redija", max_tokens=8000)

    assert "CONTESTAÇÃO" in out
    assert client._last["config"]["system_instruction"] == "sys"
    assert "redija" in str(client._last["contents"])


# ---- ClaudeProvider ----------------------------------------------------------


def _fake_anthropic_client_parse(result) -> SimpleNamespace:
    captured: dict = {}

    def _parse(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(parsed_output=result)

    client = SimpleNamespace(messages=SimpleNamespace(parse=_parse), _last=captured)
    return client


def _fake_anthropic_client_create(text: str) -> SimpleNamespace:
    captured: dict = {}

    def _create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)])

    client = SimpleNamespace(messages=SimpleNamespace(create=_create), _last=captured)
    return client


def test_claude_complete_structured_uses_parse_with_thinking_and_effort():
    expected = _Schema(rotulo="Contestação", confianca=0.9)
    client = _fake_anthropic_client_parse(expected)
    provider = llm.ClaudeProvider(client=client, model="claude-opus-4-8")

    result = provider.complete_structured(system="sys", user="classifique", schema=_Schema)

    assert result == expected
    assert client._last["model"] == "claude-opus-4-8"
    assert client._last["thinking"] == {"type": "adaptive"}
    assert client._last["output_config"] == {"effort": "high"}
    assert client._last["output_format"] is _Schema


def test_claude_complete_text_returns_text():
    client = _fake_anthropic_client_create("minuta da peça")
    provider = llm.ClaudeProvider(client=client, model="claude-opus-4-8")

    out = provider.complete_text(system="sys", user="redija", max_tokens=8000)

    assert out == "minuta da peça"
    assert client._last["model"] == "claude-opus-4-8"
    assert client._last["max_tokens"] == 8000
    assert client._last["output_config"] == {"effort": "high"}
