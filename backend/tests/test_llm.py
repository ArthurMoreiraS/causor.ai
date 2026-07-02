"""TDD for the Claude LLM transport (app/agent/llm.py)."""

from types import SimpleNamespace

from pydantic import BaseModel, Field

from app.agent import llm


class _Schema(BaseModel):
    rotulo: str
    confianca: float = Field(ge=0.0, le=1.0)


def test_get_provider_returns_claude(monkeypatch):
    monkeypatch.setattr(llm.settings, "llm_provider", "claude")
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


# --- OpenAICompatProvider (free/local testing path) ---


def _compat_response(content: str) -> dict:
    return {"choices": [{"message": {"role": "assistant", "content": content}}]}


def test_openai_compat_complete_structured_parses_json_and_validates(httpx_mock):
    httpx_mock.add_response(json=_compat_response('{"rotulo": "Contestacao", "confianca": 0.9}'))
    provider = llm.OpenAICompatProvider(
        base_url="https://api.groq.example/openai/v1",
        api_key="test-key",
        model="llama-test",
    )

    result = provider.complete_structured(system="sys", user="classifique", schema=_Schema)

    assert result == _Schema(rotulo="Contestacao", confianca=0.9)
    req = httpx_mock.get_requests()[0]
    assert req.url == "https://api.groq.example/openai/v1/chat/completions"
    assert req.headers["Authorization"] == "Bearer test-key"
    body = req.read().decode()
    assert "json_object" in body  # pede JSON mode


def test_openai_compat_complete_structured_raises_on_invalid_json(httpx_mock):
    httpx_mock.add_response(json=_compat_response("isso nao e json"))
    provider = llm.OpenAICompatProvider(
        base_url="http://localhost:11434/v1", api_key="", model="llama3"
    )

    try:
        provider.complete_structured(system="sys", user="x", schema=_Schema)
    except llm.LLMProviderError as exc:
        assert "JSON" in str(exc)
    else:
        raise AssertionError("esperava LLMProviderError para JSON invalido")


def test_openai_compat_complete_text_returns_content(httpx_mock):
    httpx_mock.add_response(json=_compat_response("minuta gerada"))
    provider = llm.OpenAICompatProvider(
        base_url="http://localhost:11434/v1", api_key="", model="llama3"
    )

    out = provider.complete_text(system="sys", user="redija", max_tokens=8000)

    assert out == "minuta gerada"
    req = httpx_mock.get_requests()[0]
    assert req.url == "http://localhost:11434/v1/chat/completions"


def test_openai_compat_caps_max_tokens_to_avoid_413(httpx_mock, monkeypatch):
    """O drafter pede 8000; o teto do provider de teste evita 413 em modelos
    com contexto menor."""
    monkeypatch.setattr(llm.settings, "llm_max_tokens", 4000)
    httpx_mock.add_response(json=_compat_response('{"rotulo": "x", "confianca": 0.5}'))
    provider = llm.OpenAICompatProvider(
        base_url="https://api.groq.example/openai/v1", api_key="k", model="llama3"
    )

    provider.complete_structured(system="s", user="u", schema=_Schema, max_tokens=8000)

    body = httpx_mock.get_requests()[0].read().decode()
    assert '"max_tokens":4000' in body


def test_openai_compat_raises_on_http_error(httpx_mock):
    httpx_mock.add_response(status_code=500)
    provider = llm.OpenAICompatProvider(
        base_url="https://api.groq.example/openai/v1", api_key="k", model="llama3"
    )

    try:
        provider.complete_text(system="s", user="u", max_tokens=100)
    except llm.LLMProviderError as exc:
        assert "HTTP" in str(exc)
    else:
        raise AssertionError("esperava LLMProviderError em falha HTTP")


def test_get_provider_switches_to_openai_compat_when_configured(monkeypatch):
    monkeypatch.setattr(llm.settings, "llm_provider", "openai_compat")
    monkeypatch.setattr(llm.settings, "llm_base_url", "http://localhost:11434/v1")
    monkeypatch.setattr(llm.settings, "llm_model", "llama3")

    provider = llm.get_provider()

    assert isinstance(provider, llm.OpenAICompatProvider)


def test_get_provider_defaults_to_claude(monkeypatch):
    monkeypatch.setattr(llm.settings, "llm_provider", "claude")
    assert isinstance(llm.get_provider(), llm.ClaudeProvider)
