"""Claude transport for the agent layer.

The agent needs two capabilities:

- ``complete_structured`` for intimation classification.
- ``complete_text`` for petition drafting.

Task-specific model selection happens in callers: Haiku for routine chat and
classification, Sonnet for drafting.

For testing without spending Claude credits, switch ``CAUSOR_LLM_PROVIDER`` to
``openai_compat`` and point ``CAUSOR_LLM_BASE_URL`` / ``CAUSOR_LLM_MODEL`` at a
free OpenAI-compatible endpoint (Groq, OpenRouter, Gemini OpenAI-compat, or a
local Ollama instance). Only the classify+draft pipeline is covered; the
agentic chat loop stays on Claude.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ValidationError

from app.settings import settings


@runtime_checkable
class LLMProvider(Protocol):
    """Transport for the model capabilities the agent layer needs."""

    def complete_structured(
        self, *, system: str, user: str, schema: type[BaseModel], max_tokens: int = 2000
    ) -> BaseModel: ...

    def complete_text(self, *, system: str, user: str, max_tokens: int) -> str: ...


class ClaudeProvider:
    """Anthropic Claude via the ``anthropic`` SDK."""

    def __init__(self, *, client=None, model: str | None = None) -> None:
        self._client = client
        self._model = model or settings.claude_model

    def _get_client(self):
        if self._client is None:
            import anthropic

            self._client = anthropic.Anthropic()
        return self._client

    def _thinking_kwargs(self) -> dict:
        # Haiku models don't support adaptive thinking / effort (400
        # invalid_request_error); Sonnet/Opus/Fable do. Classification runs on
        # Haiku (cheap/fast), drafting on Sonnet, so this must be per-call.
        if self._model.startswith("claude-haiku"):
            return {}
        return {"thinking": {"type": "adaptive"}, "output_config": {"effort": "high"}}

    def complete_structured(
        self, *, system: str, user: str, schema: type[BaseModel], max_tokens: int = 2000
    ) -> BaseModel:
        response = self._get_client().messages.parse(
            model=self._model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_format=schema,
            **self._thinking_kwargs(),
        )
        return response.parsed_output

    def complete_text(self, *, system: str, user: str, max_tokens: int) -> str:
        response = self._get_client().messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            **self._thinking_kwargs(),
        )
        return "".join(block.text for block in response.content if block.type == "text")


class LLMProviderError(RuntimeError):
    """Raised when a non-Claude provider fails to return valid output."""


class OpenAICompatProvider:
    """Any OpenAI-compatible ``/chat/completions`` endpoint (Groq, OpenRouter,
    Gemini OpenAI-compat, Ollama). Used for free/local testing.

    Structured output is done via JSON-mode prompting + Pydantic validation
    (no reliance on vendor-specific tool/parse APIs), so it works everywhere.
    """

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
        max_attempts: int | None = None,
        backoff_seconds: float | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self._base_url = (base_url or settings.llm_base_url or "").rstrip("/")
        self._api_key = api_key if api_key is not None else settings.llm_api_key
        self._model = model or settings.llm_model
        self._timeout = timeout or settings.http_timeout_seconds
        self._max_attempts = max_attempts or settings.llm_retry_attempts
        self._backoff_seconds = (
            settings.llm_retry_backoff_seconds if backoff_seconds is None else backoff_seconds
        )
        self._sleeper = sleeper
        if not self._base_url:
            raise LLMProviderError(
                "CAUSOR_LLM_BASE_URL nao configurado para openai_compat"
            )
        if not self._model:
            raise LLMProviderError(
                "CAUSOR_LLM_MODEL nao configurado para openai_compat"
            )

    def _post(self, body: dict) -> dict:
        """POST com retry em falhas transientes (429 rate-limit e 5xx de
        sobrecarga — comuns em tiers gratuitos como o Gemini free tier).
        Backoff exponencial, mesma logica de ``DjenClient._get_with_retry``.
        """
        import httpx

        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        url = f"{self._base_url}/chat/completions"

        last_error: httpx.HTTPError | None = None
        for attempt in range(1, self._max_attempts + 1):
            try:
                resp = httpx.post(url, headers=headers, json=body, timeout=self._timeout)
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_error = exc
                if attempt >= self._max_attempts:
                    break
                self._sleeper(self._backoff_seconds * (2 ** (attempt - 1)))
                continue

            if resp.status_code in {429, 500, 502, 503, 504}:
                last_error = httpx.HTTPStatusError(
                    f"Server error '{resp.status_code}'", request=resp.request, response=resp
                )
                if attempt >= self._max_attempts:
                    break
                self._sleeper(self._backoff_seconds * (2 ** (attempt - 1)))
                continue

            try:
                resp.raise_for_status()
            except httpx.HTTPError as exc:
                raise LLMProviderError(f"falha HTTP no endpoint LLM: {exc}") from exc
            return resp.json()

        raise LLMProviderError(f"falha HTTP no endpoint LLM: {last_error}")

    def _cap_tokens(self, requested: int) -> int:
        # Modelos gratuitos com contexto menor rejeitam 413 quando
        # entrada + max_tokens ultrapassa o contexto. Teto configuravel.
        cap = settings.llm_max_tokens
        if cap and requested > cap:
            return cap
        return requested

    def complete_structured(
        self, *, system: str, user: str, schema: type[BaseModel], max_tokens: int = 2000
    ) -> BaseModel:
        max_tokens = self._cap_tokens(max_tokens)
        schema_json = schema.model_json_schema()
        instruction = (
            "Responda APENAS com um objeto JSON valido seguindo este schema. "
            "Nao inclua texto fora do JSON, nem markdown, nem explicacao.\n\n"
            f"Schema:\n{json.dumps(schema_json, ensure_ascii=False)}"
        )
        messages = [
            {"role": "system", "content": system},
            {"role": "system", "content": instruction},
            {"role": "user", "content": user},
        ]
        body = {
            "model": self._model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.2,
            # json_object garante saida parseavel quando o endpoint suporta;
            # endpoints que nao reconhecem o campo normalmente o ignoram.
            "response_format": {"type": "json_object"},
        }
        data = self._post(body)
        content = _extract_content(data)
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise LLMProviderError(
                f"modelo nao retornou JSON valido: {content[:200]!r}"
            ) from exc
        try:
            return schema.model_validate(parsed)
        except ValidationError as exc:
            raise LLMProviderError(
                f"JSON retornado nao valida o schema: {exc}"
            ) from exc

    def complete_text(self, *, system: str, user: str, max_tokens: int) -> str:
        max_tokens = self._cap_tokens(max_tokens)
        body = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": max_tokens,
            "temperature": 0.3,
        }
        data = self._post(body)
        return _extract_content(data)


def _extract_content(data: dict) -> str:
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMProviderError(
            f"resposta do endpoint LLM sem choices/message/content: {str(data)[:200]!r}"
        ) from exc


def get_provider(*, model: str | None = None) -> LLMProvider:
    """Return the LLM provider configured for the requested task.

    ``model`` is the Claude task model (classification/draft). When the provider
    is ``openai_compat``, ``model`` is ignored — the single ``CAUSOR_LLM_MODEL``
    handles all tasks (fine for testing).
    """
    provider = (settings.llm_provider or "claude").strip().lower()
    if provider == "openai_compat":
        return OpenAICompatProvider()
    return ClaudeProvider(model=model)
