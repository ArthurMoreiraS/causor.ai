"""Claude transport for the agent layer.

The agent needs two capabilities:

- ``complete_structured`` for intimation classification.
- ``complete_text`` for petition drafting.

Task-specific model selection happens in callers: Haiku for routine chat and
classification, Sonnet for drafting.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel

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

    def complete_structured(
        self, *, system: str, user: str, schema: type[BaseModel], max_tokens: int = 2000
    ) -> BaseModel:
        response = self._get_client().messages.parse(
            model=self._model,
            max_tokens=max_tokens,
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


def get_provider(*, model: str | None = None) -> LLMProvider:
    """Return the Claude provider configured for the requested task."""
    return ClaudeProvider(model=model)
