"""Cliente da Jev (TypeSafe System One): perguntas tipadas, probabilidades de volta.

A Jev não gera texto. Recebe um estado e perguntas fechadas (noul = sim/não,
choice = opção de um conjunto, score = nível de uma escala) e devolve
probabilidades calibradas. Serve para decidir, nunca para calcular prazo ou
redigir. A chave é lida do ambiente (`CAUSOR_JEV_API_KEY`) na hora da chamada,
como a senha SMTP, para não entrar em `settings`, log ou diagnóstico.
"""

from __future__ import annotations

import os
import time

import httpx

BASE_URL = "https://api.typesafe.ai/v1"
DEFAULT_MODEL = "jev-latest"


class JevError(RuntimeError):
    """Falha da Jev sem detalhe sensível (nunca inclui a chave nem o estado)."""


def noul(instructions: str, *, sim: str | None = None, nao: str | None = None) -> dict:
    question: dict = {"type": "noul", "instructions": instructions}
    if sim or nao:
        question["criteria"] = {"true": sim, "false": nao}
    return question


def choice(instructions: str, options: dict[str, str]) -> dict:
    return {"type": "choice", "instructions": instructions, "criteria": options}


class JevClient:
    def __init__(self, *, api_key: str | None = None, model: str = DEFAULT_MODEL,
                 client: httpx.Client | None = None, attempts: int = 3, backoff_seconds: float = 2.0):
        key = api_key or os.environ.get("CAUSOR_JEV_API_KEY", "")
        if not key:
            raise JevError("CAUSOR_JEV_API_KEY ausente")
        self._model = model
        self._attempts = max(1, attempts)
        self._backoff = backoff_seconds
        self._client = client or httpx.Client(timeout=30.0)
        self._headers = {"Authorization": f"Bearer {key}"}

    def ask(self, state: str, questions: dict[str, dict]) -> dict:
        """Uma chamada com todas as perguntas; devolve `answers`, `model` e `usage`."""
        body = {"model": self._model, "state": state, "questions": questions}
        for attempt in range(1, self._attempts + 1):
            try:
                response = self._client.post(f"{BASE_URL}/systemone", json=body, headers=self._headers)
            except httpx.TransportError as exc:
                if attempt == self._attempts:
                    raise JevError(f"Jev indisponível: {type(exc).__name__}") from None
            else:
                if response.status_code == 200:
                    return response.json()
                if response.status_code != 429 and response.status_code < 500:
                    raise JevError(f"Jev recusou a pergunta: HTTP {response.status_code}")
                if attempt == self._attempts:
                    raise JevError(f"Jev indisponível: HTTP {response.status_code}")
            time.sleep(self._backoff * 2 ** (attempt - 1))
        raise AssertionError("unreachable")
