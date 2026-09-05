"""Prepare an offline, blinded lawyer review from app.agent.evaluate JSONL runs.

No model calls, court access or automatic legal scoring. Only share revisor/;
coordenacao/ contains the identity key and source/output hashes.
"""

import argparse
import csv
from hashlib import sha256
import json
from pathlib import Path
import random
import re


FIELDS = (
    "review_id", "caso", "minutos_fluxo_habitual", "minutos_revisao", "minutos_montagem",
    "aproveitamento", "erro_material", "omissao_critica", "fatos_sem_apoio",
    "providencia_correta", "parte_correta", "prazo_conferido", "fontes_conferidas",
    "problemas_formatacao", "causa_principal", "observacoes",
)

INSTRUCTIONS = """Revisão de minutas — rodada exploratória

Você receberá os autos e a intimação de cada caso C001, C002 etc. separadamente.
Use somente o material disponível na data da intimação. A minuta de referência
e a ficha de resposta esperada pertencem ao revisor; não entram no prompt.

1. Leia os arquivos R001.txt, R002.txt etc. na ordem numérica. Registre o tempo
   ativo para conferir fontes e corrigir a minuta até ela ficar utilizável.
2. Preencha avaliacoes.csv. Campos vazios significam não avaliado, nunca zero.
3. Aproveitamento: localizada / reescrita / rejeitada / falha_geracao.
   Erro material, omissão crítica e fatos sem apoio: sim / nao / incerto.
   Providência/parte corretas: sim / nao / incerto / nao_aplicavel.
   Prazo/fontes conferidos: sim / nao / nao_aplicavel.
4. Registre erro, trecho e fonte/página nas observações. Verifique também prova
   contrária, decisão superada e informação que depende do cliente.
5. Causa principal: documento_ausente / extracao / recuperacao / interpretacao /
   redacao / formatacao / outra. A causa é uma hipótese para investigar.
6. O tempo do fluxo habitual deve ser medido separadamente para o mesmo recorte;
   se só houver estimativa, identifique-a nas observações. Não invente baseline.
7. Se a providência correta não exige petição, registre isso; não aprove uma peça
   desnecessária só porque está bem escrita. Falha de geração também conta.

Não consulte a chave da coordenação durante a revisão. Modelos podem deixar
pistas no próprio texto; a preparação remove metadados, não promete cegamento
perfeito. Casos e documentos permanecem no ambiente autorizado do escritório.
Cinco casos servem para descobrir falhas e ajustar o recorte, não para homologar
qualidade jurídica, autonomia ou integração com tribunal.
"""


def prepare_review(runs: list[dict], output: Path) -> None:
    if not runs:
        raise ValueError("nenhuma execução para revisar")
    seen = set()
    for run in runs:
        if not isinstance(run, dict):
            raise ValueError("execução deve ser um objeto JSON")
        if not all(isinstance(run.get(k), str) and run[k] for k in ("case_id", "input_sha256", "provider", "model")):
            raise ValueError("execução sem identificação ou hash")
        if not re.fullmatch(r"[a-f0-9]{64}", run["input_sha256"]):
            raise ValueError("hash de entrada inválido")
        if run.get("status") not in {"completed", "failed"}:
            raise ValueError("status de execução inválido")
        if run["status"] == "completed":
            draft = run.get("output")
            if not isinstance(draft, dict) or not isinstance(draft.get("minuta"), str) or not draft["minuta"].strip():
                raise ValueError("execução concluída sem minuta")
            if (any(not isinstance(draft.get(field, ""), str) for field in ("contexto_consolidado", "analise_providencia"))
                    or not isinstance(draft.get("alertas", []), list)
                    or any(not isinstance(a, str) for a in draft.get("alertas", []))):
                raise ValueError("conteúdo de revisão inválido")
        identity = tuple(run[k] for k in ("case_id", "input_sha256", "provider", "model"))
        if identity in seen:
            raise ValueError("execução duplicada; use outra rodada para repetições")
        seen.add(identity)

    ordered = list(runs)
    random.SystemRandom().shuffle(ordered)
    cases = {case: f"C{i:03d}" for i, case in enumerate(sorted({r["case_id"] for r in runs}), 1)}
    output.mkdir(parents=True, exist_ok=False)
    reviewer, coordinator = output / "revisor", output / "coordenacao"
    reviewer.mkdir()
    coordinator.mkdir()
    key, rows = [], []
    for i, run in enumerate(ordered, 1):
        review_id, case_alias = f"R{i:03d}", cases[run["case_id"]]
        text = f"Avaliação {review_id} | Caso {case_alias}\n\n"
        if run["status"] == "failed":
            text += "Não foi possível gerar esta minuta. Registre falha_geracao no aproveitamento.\n"
        else:
            draft = run["output"]
            # Whitelist the legal content; omit model/provider/confidence/latency metadata.
            for label, field in (("Contexto", "contexto_consolidado"), ("Providência", "analise_providencia"),
                                 ("Minuta", "minuta")):
                text += f"{label}\n\n{draft.get(field, '')}\n\n"
            text += "Alertas\n\n" + "\n".join(str(a) for a in draft.get("alertas", [])) + "\n"
        data = text.encode("utf-8")
        (reviewer / f"{review_id}.txt").write_bytes(data)
        key.append({"review_id": review_id, "caso": case_alias,
                    **{field: run.get(field) for field in ("case_id", "input_sha256", "provider", "model", "status", "latency_ms")},
                    "review_file_sha256": sha256(data).hexdigest(),
                    "run_sha256": sha256(json.dumps(run, sort_keys=True, ensure_ascii=False).encode()).hexdigest()})
        rows.append({"review_id": review_id, "caso": case_alias})
    with (reviewer / "avaliacoes.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    (reviewer / "LEIA-ME.txt").write_text(INSTRUCTIONS, encoding="utf-8")
    (coordinator / "chave.json").write_text(json.dumps(key, ensure_ascii=False, indent=2), encoding="utf-8")
    (coordinator / "LEIA-ME.txt").write_text(
        "Não compartilhar esta pasta durante a revisão. Entregue os autos/intimação com os códigos C001 etc.\n"
        "Compare modelos apenas quando case_id e input_sha256 forem iguais. Hash diferente é outro contexto.\n"
        "Some falhas de geração ao denominador. Não trate campos vazios como aprovação.\n"
        "Meça tempo total ativo; qualquer erro material exige análise antes de ampliar o piloto.\n"
        "O CSV é registro humano; não há agregação automática nem aprovação jurídica neste comando.\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        runs = [json.loads(line) for path in args.runs
                for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        prepare_review(runs, args.output)
    except (ValueError, FileExistsError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
