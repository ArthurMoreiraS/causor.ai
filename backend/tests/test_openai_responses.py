import json

import httpx
import pytest
from pydantic import BaseModel


class Answer(BaseModel):
    text: str


def test_responses_uses_strict_schema_and_records_usage_without_prompt(monkeypatch):
    from app.agent.openai_responses import OpenAIResponsesProvider

    def post(url, *, json, **kwargs):
        assert url == "https://api.openai.com/v1/responses"
        assert json["model"] == "gpt-6-astra"
        assert json["store"] is False
        assert "temperature" not in json
        assert json["text"]["format"]["schema"]["additionalProperties"] is False
        return httpx.Response(200, request=httpx.Request("POST", url), json={
            "status": "completed", "model": "gpt-6-astra", "usage": {"input_tokens": 20, "output_tokens": 10},
            "output": [{"type": "reasoning"}, {"type": "message", "content": [
                {"type": "output_text", "text": '{"text":"ok"}'}
            ]}],
        })

    monkeypatch.setattr(httpx, "post", post)
    provider = OpenAIResponsesProvider(api_key="test")
    assert provider.complete_structured(system="regras", user="sigiloso", schema=Answer).text == "ok"
    assert provider.last_call["usage"]["input_tokens"] == 20
    assert "sigiloso" not in json.dumps(provider.last_call)


@pytest.mark.parametrize("status,content", [
    ("incomplete", [{"type": "output_text", "text": '{"text":"parcial"}'}]),
    ("completed", [{"type": "refusal", "refusal": "recusa"}]),
])
def test_partial_or_refused_responses_fail_closed(monkeypatch, status, content):
    from app.agent.openai_responses import OpenAIResponsesProvider
    from app.agent.llm import LLMProviderError

    monkeypatch.setattr(httpx, "post", lambda url, **kw: httpx.Response(
        200, request=httpx.Request("POST", url), json={
            "status": status, "output": [{"type": "message", "content": content}],
        },
    ))
    with pytest.raises(LLMProviderError):
        OpenAIResponsesProvider(api_key="test").complete_structured(system="", user="", schema=Answer)
