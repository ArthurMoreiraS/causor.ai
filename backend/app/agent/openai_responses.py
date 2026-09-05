"""OpenAI Responses, opt-in por tarefa. Sem ferramentas ou ações externas.

Referências: developers.openai.com/api/docs/guides/structured-outputs e
developers.openai.com/api/docs/guides/latest-model?model=gpt-6-astra.
"""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import logging
import os
import time

import httpx
from pydantic import BaseModel, ValidationError

from app.agent.llm import LLMProviderError
from app.settings import settings


def _strict_schema(schema: dict) -> dict:
    result = deepcopy(schema)

    def visit(node):
        if isinstance(node, dict):
            node.pop("default", None)
            if node.get("type") == "object":
                node["additionalProperties"] = False
                node["required"] = list(node.get("properties", {}))
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for value in node:
                visit(value)

    visit(result)
    return result


class OpenAIResponsesProvider:
    def __init__(self, *, model: str | None = None, api_key: str | None = None):
        self._model = model or settings.openai_model
        self._api_key = api_key if api_key is not None else os.environ.get("OPENAI_API_KEY", "")
        self.last_call: dict = {}

    def _complete(self, *, system: str, user: str, max_tokens: int, schema=None) -> str:
        if not self._api_key:
            raise LLMProviderError("OPENAI_API_KEY não configurada")
        body = {
            "model": self._model, "instructions": system, "input": user,
            "store": False, "max_output_tokens": max_tokens,
            "reasoning": {"effort": settings.openai_reasoning_effort},
        }
        if schema is not None:
            body["text"] = {"format": {
                "type": "json_schema", "name": schema.__name__, "strict": True,
                "schema": _strict_schema(schema.model_json_schema()),
            }}
        started = time.monotonic()
        self.last_call = {
            "provider": "openai", "model": self._model,
            "task_schema": schema.__name__ if schema else "text",
            "prompt_version": sha256(system.encode()).hexdigest()[:16],
            "status": "failed",
        }
        try:
            for attempt in range(max(1, settings.llm_retry_attempts)):
                try:
                    response = httpx.post(
                        "https://api.openai.com/v1/responses", json=body,
                        headers={"Authorization": f"Bearer {self._api_key}"},
                        timeout=settings.http_timeout_seconds,
                    )
                    response.raise_for_status()
                    break
                except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
                    retryable = not isinstance(exc, httpx.HTTPStatusError) or exc.response.status_code in {429, 500, 502, 503, 504}
                    if not retryable or attempt + 1 >= settings.llm_retry_attempts:
                        raise LLMProviderError("openai_request_failed") from exc
                    time.sleep(settings.llm_retry_backoff_seconds * (2 ** attempt))
            data = response.json()
            self.last_call.update({"model": data.get("model", self._model), "usage": data.get("usage", {})})
            if data.get("status") != "completed":
                raise LLMProviderError("openai_response_incomplete")
            blocks = [block for item in data.get("output", []) if item.get("type") == "message" for block in item.get("content", [])]
            if any(block.get("type") == "refusal" for block in blocks):
                raise LLMProviderError("openai_response_refused")
            text = "".join(block.get("text", "") for block in blocks if block.get("type") == "output_text")
            if not text:
                raise LLMProviderError("openai_empty_response")
            if schema is not None:
                try:
                    schema.model_validate_json(text)
                except ValidationError as exc:
                    raise LLMProviderError("openai_invalid_structured_output") from exc
            self.last_call["status"] = "completed"
            return text
        except Exception as exc:
            self.last_call["error"] = type(exc).__name__
            raise
        finally:
            self.last_call["latency_ms"] = round((time.monotonic() - started) * 1000)
            logging.getLogger(__name__).info("llm_call %s", json.dumps(self.last_call))

    def complete_structured(self, *, system: str, user: str, schema: type[BaseModel], max_tokens: int = 2000) -> BaseModel:
        return schema.model_validate_json(self._complete(system=system, user=user, schema=schema, max_tokens=max_tokens))

    def complete_text(self, *, system: str, user: str, max_tokens: int) -> str:
        return self._complete(system=system, user=user, max_tokens=max_tokens)
