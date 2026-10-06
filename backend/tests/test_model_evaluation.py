import json
from types import SimpleNamespace

from app.agent import evaluate


def test_comparison_uses_same_case_and_distinct_models(tmp_path, monkeypatch):
    cases = tmp_path / "cases.jsonl"
    cases.write_text(json.dumps({"id": "synthetic", "intimacao_texto": "Teor fictício",
                                "classificacao": {"tipo": "Contestação", "peticao_sugerida": "Contestação",
                                                  "prazo_dias": 15, "dias_uteis": True, "confianca": 0.8,
                                                  "resumo": "Fixture"}, "contexto_processo": {}}))
    output = tmp_path / "result.jsonl"
    monkeypatch.setattr("sys.argv", ["evaluate", "--cases", str(cases), "--output", str(output),
                                   "--provider", "claude", "--claude-model", "claude-sonnet-5",
                                   "--claude-model", "claude-sonnet-5-5"])
    monkeypatch.setattr(evaluate, "ClaudeProvider", lambda model: SimpleNamespace(_model=model))
    def draft(**kwargs):
        return SimpleNamespace(model_dump=lambda: {"llm": {"model": kwargs["provider"]._model,
                                                          "usage": {"input_tokens": 10, "output_tokens": 20}}})
    monkeypatch.setattr(evaluate, "draft_peticao", draft)
    assert evaluate.main() == 0
    rows = [json.loads(line) for line in output.read_text().splitlines()]
    assert [r["model"] for r in rows] == ["claude-sonnet-5", "claude-sonnet-5-5"]
    assert rows[0]["input_sha256"] == rows[1]["input_sha256"]
    assert all(r["output"]["llm"]["usage"]["output_tokens"] == 20 for r in rows)
