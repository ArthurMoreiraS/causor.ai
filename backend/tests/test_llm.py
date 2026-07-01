"""TDD for the Claude LLM transport (app/agent/llm.py)."""

from types import SimpleNamespace

from pydantic import BaseModel, Field

from app.agent import llm


class _Schema(BaseModel):
    rotulo: str
    confianca: float = Field(ge=0.0, le=1.0)


def test_get_provider_returns_claude():
    provider = llm.get_provider()
    assert isinstance(provider, llm.ClaudeProvider)


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
    expected = _Schema(rotulo="Contestacao", confianca=0.9)
    client = _fake_anthropic_client_parse(expected)
    provider = llm.ClaudeProvider(client=client, model="claude-haiku-4-5")

    result = provider.complete_structured(system="sys", user="classifique", schema=_Schema)

    assert result == expected
    assert client._last["model"] == "claude-haiku-4-5"
    assert client._last["thinking"] == {"type": "adaptive"}
    assert client._last["output_config"] == {"effort": "high"}
    assert client._last["output_format"] is _Schema
    assert client._last["max_tokens"] == 2000  # default for classification


def test_claude_complete_structured_forwards_max_tokens():
    client = _fake_anthropic_client_parse(_Schema(rotulo="Contestacao", confianca=0.9))
    provider = llm.ClaudeProvider(client=client, model="claude-sonnet-4-6")

    provider.complete_structured(system="sys", user="redija", schema=_Schema, max_tokens=8000)

    assert client._last["max_tokens"] == 8000  # drafting needs the larger budget


def test_claude_complete_text_returns_text():
    client = _fake_anthropic_client_create("minuta da peca")
    provider = llm.ClaudeProvider(client=client, model="claude-sonnet-4-6")

    out = provider.complete_text(system="sys", user="redija", max_tokens=8000)

    assert out == "minuta da peca"
    assert client._last["model"] == "claude-sonnet-4-6"
    assert client._last["max_tokens"] == 8000
    assert client._last["output_config"] == {"effort": "high"}
