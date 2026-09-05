import csv
import json

import pytest

from app.agent.prepare_review import prepare_review


def _run(model="modelo-a", **changes):
    return {"case_id": "caso-original", "input_sha256": "a" * 64, "provider": "provider-a",
            "model": model, "status": "completed", "latency_ms": 100,
            "output": {"minuta": "Texto para revisão.", "analise_providencia": "Conferir documentos.",
                       "contexto_consolidado": "Contexto fornecido.", "alertas": ["Documento ausente."],
                       "llm": {"model": model}, "confianca": 0.99}, **changes}


def test_review_packet_hides_metadata_and_preserves_blind_mapping(tmp_path):
    target = tmp_path / "rodada"
    prepare_review([_run(), _run("modelo-b", provider="provider-b")], target)
    public_text = "\n".join(p.read_text(encoding="utf-8-sig") for p in (target / "revisor").iterdir())
    assert "Texto para revisão." in public_text and "Documento ausente." in public_text
    assert "modelo-a" not in public_text and "modelo-b" not in public_text
    assert "0.99" not in public_text and "provider-a" not in public_text
    key = json.loads((target / "coordenacao/chave.json").read_text(encoding="utf-8"))
    assert {r["model"] for r in key} == {"modelo-a", "modelo-b"}
    assert len({r["review_id"] for r in key}) == 2
    assert len({r["input_sha256"] for r in key}) == 1
    assert all(len(r["review_file_sha256"]) == 64 for r in key)
    with (target / "revisor/avaliacoes.csv").open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 2 and all(r["minutos_revisao"] == "" for r in rows)


def test_failures_are_included_in_review_denominator(tmp_path):
    prepare_review([_run(status="failed", output=None, error="ProviderError")], tmp_path / "rodada")
    text = next((tmp_path / "rodada/revisor").glob("R*.txt")).read_text(encoding="utf-8")
    assert "Não foi possível gerar" in text


def test_duplicate_runs_are_rejected_before_writing(tmp_path):
    with pytest.raises(ValueError, match="duplicada"):
        prepare_review([_run(), _run()], tmp_path / "rodada")
    assert not (tmp_path / "rodada").exists()


def test_review_never_overwrites_existing_round(tmp_path):
    target = tmp_path / "rodada"
    prepare_review([_run()], target)
    with pytest.raises(FileExistsError):
        prepare_review([_run()], target)


@pytest.mark.parametrize("run", [42, _run(output={"minuta": "Texto", "alertas": None}), _run(input_sha256="sem-hash")])
def test_invalid_inputs_do_not_leave_partial_review(tmp_path, run):
    with pytest.raises(ValueError):
        prepare_review([run], tmp_path / "rodada")
    assert not (tmp_path / "rodada").exists()
