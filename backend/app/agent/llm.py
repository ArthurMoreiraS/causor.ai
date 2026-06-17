"""Provider-agnostic LLM seam for the agent layer.

Two capabilities the agent needs from a text model:

- ``complete_structured`` — classification (validated structured/JSON output).
- ``complete_text`` — petition drafting (free-form text).

Gemini is the current default (provisional); Claude stays available behind the
same interface. Adding a new model later is a new ``LLMProvider`` class plus one
branch in ``get_provider`` and an env var — callers never change.

Secrets never reach a provider: callers whitelist what goes into ``system`` and
``user`` before calling. Providers only transport text.
"""

from __future__ import annotations

import json
from typing import Protocol, runtime_checkable

from annotated_types import Ge, Le
from pydantic import BaseModel

from app.settings import settings


@runtime_checkable
class LLMProvider(Protocol):
    """Transport for the two model capabilities the agent layer needs."""

    def complete_structured(
        self, *, system: str, user: str, schema: type[BaseModel]
    ) -> BaseModel: ...

    def complete_text(self, *, system: str, user: str, max_tokens: int) -> str: ...


def _clamp_to_schema(data: dict, schema: type[BaseModel]) -> dict:
    """Clamp numeric values into any ``ge``/``le`` bounds declared on the schema.

    Some providers (Gemini's JSON mode) ignore numeric constraints, so a model
    may emit e.g. confianca=1.7 for a field bounded to [0, 1]. We clamp before
    pydantic validation so a slightly off value never hard-fails the request.
    """
    for name, field in schema.model_fields.items():
        if name not in data or not isinstance(data[name], (int, float)):
            continue
        low = high = None
        for meta in field.metadata:
            if isinstance(meta, Ge):
                low = meta.ge
            elif isinstance(meta, Le):
                high = meta.le
        value = data[name]
        if low is not None:
            value = max(value, low)
        if high is not None:
            value = min(value, high)
        data[name] = value
    return data


class GeminiProvider:
    """Google Gemini via the ``google-genai`` SDK."""

    def __init__(self, *, client=None, model: str | None = None) -> None:
        self._client = client
        self._model = model or settings.gemini_model

    def _get_client(self):
        if self._client is None:
            from google import genai

            self._client = genai.Client()
        return self._client

    def complete_structured(
        self, *, system: str, user: str, schema: type[BaseModel]
    ) -> BaseModel:
        response = self._get_client().models.generate_content(
            model=self._model,
            contents=user,
            config={
                "system_instruction": system,
                "response_mime_type": "application/json",
                "response_schema": schema,
            },
        )
        data = _clamp_to_schema(json.loads(response.text), schema)
        return schema.model_validate(data)

    def complete_text(self, *, system: str, user: str, max_tokens: int) -> str:
        response = self._get_client().models.generate_content(
            model=self._model,
            contents=user,
            config={"system_instruction": system, "max_output_tokens": max_tokens},
        )
        return response.text or ""


class ClaudeProvider:
    """Anthropic Claude via the ``anthropic`` SDK (adaptive thinking, high effort)."""

    def __init__(self, *, client=None, model: str | None = None) -> None:
        self._client = client
        self._model = model or settings.claude_model

    def _get_client(self):
        if self._client is None:
            import anthropic

            self._client = anthropic.Anthropic()
        return self._client

    def complete_structured(
        self, *, system: str, user: str, schema: type[BaseModel]
    ) -> BaseModel:
        response = self._get_client().messages.parse(
            model=self._model,
            max_tokens=2000,
            thinking={"type": "adaptive"},
            output_config={"effort": "high"},
            system=system,
            messages=[{"role": "user", "content": user}],
            output_format=schema,
        )
        return response.parsed_output

    def complete_text(self, *, system: str, user: str, max_tokens: int) -> str:
        response = self._get_client().messages.create(
            model=self._model,
            max_tokens=max_tokens,
            thinking={"type": "adaptive"},
            output_config={"effort": "high"},
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(block.text for block in response.content if block.type == "text")


def get_provider(name: str | None = None) -> LLMProvider:
    """Return the configured provider. Default comes from ``settings.llm_provider``."""
    name = (name or settings.llm_provider).strip().lower()
    if name == "gemini":
        return GeminiProvider()
    if name == "claude":
        return ClaudeProvider()
    raise ValueError(f"provider LLM desconhecido: {name!r} (use 'gemini' ou 'claude')")
