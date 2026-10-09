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


# Perguntas sobre o teor de uma intimação; a bancada usa as mesmas.
PERGUNTAS_INTIMACAO = {
    "prazo_expresso": noul(
        "A comunicação fixa, por escrito, um prazo em dias para alguma parte praticar um ato.",
        sim="O texto diz o número de dias (ex.: 'no prazo de 15 dias', 'em cinco dias').",
        nao="Não há número de dias escrito; o prazo, se houver, decorre da lei ou do tipo de ato.",
    ),
    "multiplos_atos": noul(
        "A comunicação determina mais de um ato, ou intima mais de uma parte com providências ou prazos distintos.",
        sim="Há duas ou mais ordens distintas, ou partes diferentes com prazos diferentes.",
        nao="Há uma única ordem dirigida a uma parte, ou nenhuma ordem.",
    ),
    "exige_providencia": noul(
        "A comunicação exige que o advogado intimado pratique algum ato processual.",
        sim="Há algo a fazer: manifestar, recorrer, juntar, pagar, comparecer.",
        nao="É mera ciência, pauta, distribuição ou expediente sem ordem à parte.",
    ),
}
# Na bancada de 09/10, 6 de 40 prazos em vigor passaram deste limiar.
LIMIAR_AVISO = 0.9
AVISO_MULTIPLOS = "O texto parece trazer mais de um ato ou parte; confira a qual o prazo se refere."


def notice_state(text: str, context: dict | None = None) -> str:
    from app.agent.deadline_interpretation import text_for_model

    context = context or {}
    meta = f"Tribunal: {context.get('tribunal') or '-'}. Tipo: {context.get('tipo_comunicacao') or '-'}."
    return f"{meta}\nComunicação DJEN:\n{text_for_model(text)}"


def assess_notice(text: str, context: dict | None = None) -> dict | None:
    """Avisos da Jev sobre uma intimação. Só acrescenta avisos; nunca muda prazo.

    Sem chave devolve None; qualquer falha vira {"status": "falha"} sem
    interromper a análise. Uma tentativa curta: o aviso não vale um worker parado.
    """
    if not os.environ.get("CAUSOR_JEV_API_KEY"):
        return None
    try:
        with httpx.Client(timeout=10.0) as http:
            response = JevClient(client=http, attempts=1).ask(notice_state(text, context), PERGUNTAS_INTIMACAO)
        answers = {key: float(response["answers"][key]["noul"]) for key in PERGUNTAS_INTIMACAO}
    except (JevError, KeyError, TypeError, ValueError):
        return {"status": "falha"}
    avisos = [AVISO_MULTIPLOS] if answers["multiplos_atos"] >= LIMIAR_AVISO else []
    return {"status": "ok", "modelo": response.get("model"), **answers, "avisos": avisos}
