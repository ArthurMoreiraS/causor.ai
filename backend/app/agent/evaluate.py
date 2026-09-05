"""Avaliação pareada com contexto fixo. Só chama APIs ao executar este comando.

python -m app.agent.evaluate --cases casos.jsonl --output artifacts/evals/resultado.jsonl
    --provider claude --provider openai
Cada linha de casos: id, intimacao_texto, classificacao, contexto_processo,
historico (opcional), prazo_fatal (opcional), template_conteudo (opcional).
Os arquivos contêm material jurídico e devem permanecer no ambiente autorizado.
"""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import time

from app.agent.classifier import ClassificacaoIntimacao
from app.agent.drafter import draft_peticao
from app.agent.llm import ClaudeProvider, OpenAICompatProvider
from app.agent.openai_responses import OpenAIResponsesProvider
from app.settings import settings


def evaluate_case(case: dict, provider) -> dict:
    """Mesmos dados e prompt do redator; mede execução, não mérito jurídico."""
    started = time.monotonic()
    result = {"case_id": case["id"], "input_sha256": sha256(
        json.dumps(case, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest(), "model": getattr(provider, "_model", "test")}
    try:
        draft = draft_peticao(
            intimacao_texto=case["intimacao_texto"],
            classificacao=ClassificacaoIntimacao.model_validate(case["classificacao"]),
            contexto_processo=case["contexto_processo"], historico=case.get("historico"),
            prazo_fatal=case.get("prazo_fatal"), template_conteudo=case.get("template_conteudo"),
            provider=provider,
        )
        result.update(status="completed", output=draft.model_dump())
    except Exception as exc:
        result.update(status="failed", error=type(exc).__name__)
    result["latency_ms"] = round((time.monotonic() - started) * 1000)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--provider", action="append", required=True, choices=["claude", "openai", "openai_compat"])
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    if args.limit < 1:
        parser.error("--limit deve ser positivo")
    providers = {"claude": lambda: ClaudeProvider(model=settings.claude_draft_model),
                 "openai": OpenAIResponsesProvider, "openai_compat": OpenAICompatProvider}
    cases = [json.loads(line) for line in args.cases.read_text(encoding="utf-8").splitlines() if line.strip()]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    failed = False
    with args.output.open("x", encoding="utf-8") as target:
        for case in cases[:args.limit]:
            for name in args.provider:
                result = evaluate_case(case, providers[name]())
                failed |= result["status"] == "failed"
                target.write(json.dumps({"provider": name, **result}, ensure_ascii=False) + "\n")
                target.flush()
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
