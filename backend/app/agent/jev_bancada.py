"""Bancada da Jev contra a análise de prazo atual. Não altera o banco nem a produção.

Três passos, executados de `backend/`:

    python -m app.agent.jev_bancada exportar --output artifacts/evals/jev/intimacoes.jsonl
    python -m app.agent.jev_bancada rodar --cases artifacts/evals/jev/intimacoes.jsonl
    python -m app.agent.jev_bancada relatorio --dir artifacts/evals/jev

`exportar` lê intimações e a análise gravada (`_causor_prazo`) numa transação
somente leitura. `rodar` faz uma chamada à Jev por intimação (retomável), grava
`resultados.jsonl` e a planilha `rotulos.csv` para rotulagem às cegas: ela não
mostra as respostas da Jev. `relatorio` cruza Causor, Jev e rótulos.

A Jev só pode tornar a decisão mais cautelosa. A pergunta desta bancada é:
nos prazos que o Causor pôs em vigor sozinho, ela pega os errados sem
alarmar demais os certos? Os arquivos têm teor de publicações e ficam em
`backend/artifacts/`, fora do git.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import random
import sys
import time

from app.agent.deadline_interpretation import text_for_model
from app.agent.jev import DEFAULT_MODEL, JevClient, JevError, choice, noul
from app.capture.text import html_to_text
from app.prazo_engine.atos import ATOS

VIGENTE = {"calculado_a_revisar", "confirmado"}
EM_ANDAMENTO = {"sem_analise", "analisando", "falha"}
LIMIAR = 0.5
SIM_NAO = {"s": True, "n": False}

ATO_DESCRICOES = {
    "sentenca": "Sentença: decisão que encerra a fase de conhecimento ou a execução no primeiro grau",
    "acordao": "Acórdão: julgamento colegiado de tribunal",
    "decisao_interlocutoria": "Decisão interlocutória do juiz de primeiro grau no curso do processo",
    "decisao_monocratica_tribunal": "Decisão monocrática de relator ou presidente de tribunal",
    "inadmissao_recurso_excepcional": "Decisão que não admite recurso especial ou extraordinário",
    "intimacao_manifestacao": "Despacho ou ato que manda a parte se manifestar, juntar, emendar ou cumprir algo",
    "pauta_julgamento": "Inclusão em pauta ou designação de sessão de julgamento",
    "distribuicao_ou_expediente": "Distribuição, redistribuição ou expediente sem ordem à parte",
    "citacao": "Citação da parte para integrar o processo",
    "outro": "Nenhuma das anteriores",
}
assert set(ATO_DESCRICOES) == set(ATOS)

RITO_DESCRICOES = {
    "comum": "Processo civil pelo CPC (procedimento comum, execução, cumprimento de sentença)",
    "juizado": "Juizado especial cível ou da fazenda pública",
    "trabalhista": "Justiça do Trabalho (CLT)",
    "criminal": "Processo penal",
    "outro": "Outro regime processual",
}

PERGUNTAS = {
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
    "ato": choice("Natureza do ato comunicado", ATO_DESCRICOES),
    "rito": choice("Regime processual do caso", RITO_DESCRICOES),
}

ROTULOS = ("r_prazo_causor_correto", "r_prazo_expresso", "r_multiplos_atos", "r_ato", "r_rito", "r_observacao")


def _estado(case: dict) -> str:
    meta = f"Tribunal: {case.get('tribunal') or '-'}. Tipo: {case.get('tipo_comunicacao') or '-'}."
    return f"{meta}\nComunicação DJEN:\n{text_for_model(case['teor'])}"


def causor_view(analise: dict | None) -> dict:
    """Decisões do Causor já gravadas, no vocabulário das perguntas."""
    analise = analise or {}
    vigente = analise.get("status") in VIGENTE and bool(analise.get("prazo_id"))
    return {
        "status": analise.get("status"),
        "vigente": vigente,
        "dias": analise.get("dias"),
        "origem_duracao": analise.get("origem_duracao"),
        "fundamento": analise.get("fundamento"),
        "prazo_expresso": analise.get("origem_duracao") == "judicial_expressa",
        "multiplos_atos": "Múltiplos atos" in (analise.get("motivo") or ""),
        "ato": analise.get("ato"),
        "rito": analise.get("rito"),
        "confianca": analise.get("confianca"),
    }


def jev_view(answers: dict) -> dict:
    view = {key: answers[key]["noul"] for key in ("prazo_expresso", "multiplos_atos", "exige_providencia")}
    for key in ("ato", "rito"):
        view[key] = answers[key]["choice"]
        view[f"{key}_confianca"] = answers[key].get("confidence")
    return view


def alertas(causor: dict, jev: dict) -> list[str]:
    """Motivos pelos quais a Jev mandaria um prazo em vigor para triagem."""
    if not causor["vigente"]:
        return []
    found = []
    expressa = causor["origem_duracao"] == "judicial_expressa"
    if jev["multiplos_atos"] >= LIMIAR:
        found.append("multiplos_atos")
    if expressa and jev["prazo_expresso"] < LIMIAR:
        found.append("sem_prazo_expresso")
    # Prazo pelo tipo de ato só existe quando o prazo escrito não foi confirmado;
    # se o teor tem número de dias, a duração padrão do ato é suspeita.
    if causor["origem_duracao"] == "regra_por_ato" and jev["prazo_expresso"] >= LIMIAR:
        found.append("prazo_escrito_no_teor")
    # Sentença e acórdão não ordenam nada ao advogado; o prazo de recurso vem
    # do tipo de ato. Só uma ordem judicial expressa pressupõe providência.
    if expressa and jev["exige_providencia"] < LIMIAR:
        found.append("sem_providencia")
    if causor["ato"] and jev["ato"] != causor["ato"]:
        found.append("ato_divergente")
    if causor["rito"] in RITO_DESCRICOES and jev["rito"] != causor["rito"]:
        found.append("rito_divergente")
    return found


def exportar(output: Path, *, limit: int, escritorio: int | None) -> int:
    from sqlalchemy import select, text

    from app.sor import models
    from app.sor.db import SessionLocal

    query = (select(models.Intimacao).where(models.Intimacao.teor.is_not(None))
             .order_by(models.Intimacao.id.desc()).limit(limit))
    if escritorio is not None:
        query = query.where(models.Intimacao.escritorio_id == escritorio)
    output.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    statuses: dict[str, int] = {}
    with SessionLocal() as session, output.open("w", encoding="utf-8") as file:
        session.execute(text("SET TRANSACTION READ ONLY"))
        for notice in session.scalars(query):
            status = (notice.prazo_analise or {}).get("status") or "sem_analise"
            statuses[status] = statuses.get(status, 0) + 1
            file.write(json.dumps({
                "id": notice.id, "numero_processo": notice.numero_processo, "tribunal": notice.tribunal,
                "tipo_comunicacao": notice.tipo_comunicacao, "teor": notice.teor,
                "data_disponibilizacao": notice.data_disponibilizacao.isoformat() if notice.data_disponibilizacao else None,
                "analise": notice.prazo_analise,
            }, ensure_ascii=False) + "\n")
            count += 1
        if not count:
            _diagnostico(session)
        session.rollback()
    print(f"Análise de prazo por status: {statuses}", file=sys.stderr)
    waiting = sum(statuses.get(status, 0) for status in EM_ANDAMENTO)
    if waiting:
        print(f"{waiting} ainda sem decisão do Causor; a bancada as ignora. "
              "Exporte de novo quando a análise terminar.", file=sys.stderr)
    return count


def _diagnostico(session) -> None:
    """Só contagens, para explicar uma exportação vazia sem expor conteúdo."""
    from sqlalchemy import func, select

    from app.sor import models

    url = session.get_bind().url
    total = session.scalar(select(func.count()).select_from(models.Intimacao))
    com_teor = session.scalar(select(func.count()).where(models.Intimacao.teor.is_not(None)))
    por_escritorio = session.execute(select(models.Intimacao.escritorio_id, func.count())
                                     .group_by(models.Intimacao.escritorio_id)).all()
    oabs = session.scalar(select(func.count()).select_from(models.OabMonitorada))
    print(f"Banco: {url.host}/{url.database} (usuário {url.username})", file=sys.stderr)
    print(f"Intimações: {total} no total, {com_teor} com teor; por escritório: {dict(por_escritorio)}",
          file=sys.stderr)
    print(f"OABs monitoradas: {oabs}", file=sys.stderr)


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def rodar(cases_path: Path, out_dir: Path, *, client: JevClient, amostra: int, seed: int = 7) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    results_path = out_dir / "resultados.jsonl"
    done = {row["id"] for row in _read_jsonl(results_path) if row.get("status") == "ok"}
    cases = [case for case in _read_jsonl(cases_path)
             if ((case.get("analise") or {}).get("status") or "sem_analise") not in EM_ANDAMENTO]
    with results_path.open("a", encoding="utf-8") as file:
        for case in cases:
            if case["id"] in done:
                continue
            started = time.monotonic()
            row = {"id": case["id"], "causor": causor_view(case.get("analise"))}
            try:
                response = client.ask(_estado(case), PERGUNTAS)
                row["jev"] = jev_view(response["answers"])
                row.update(status="ok", modelo=response.get("model"), usage=response.get("usage"),
                           alertas=alertas(row["causor"], row["jev"]))
            except (JevError, KeyError) as exc:
                row.update(status="falha", erro=str(exc) if isinstance(exc, JevError) else "resposta_inesperada")
            row["latencia_ms"] = round((time.monotonic() - started) * 1000)
            file.write(json.dumps(row, ensure_ascii=False) + "\n")
    results = _latest(_read_jsonl(results_path))
    _write_label_sheet(out_dir / "rotulos.csv", cases, results, amostra=amostra, seed=seed)
    return resumo(results)


def _latest(rows: list[dict]) -> dict[int, dict]:
    """Última resposta válida por intimação; alertas recalculados com a regra atual."""
    latest: dict[int, dict] = {}
    for row in rows:
        if row.get("status") == "ok" or row["id"] not in latest:
            latest[row["id"]] = row
    for row in latest.values():
        if row.get("status") == "ok":
            row["alertas"] = alertas(row["causor"], row["jev"])
    return latest


def _write_label_sheet(path: Path, cases: list[dict], results: dict[int, dict], *, amostra: int, seed: int) -> None:
    """Amostra estratificada: metade com alerta da Jev, resto sorteado. Sem respostas da Jev."""
    if path.exists():
        return  # nunca sobrescrever rótulos já feitos
    ok = [case for case in cases if results.get(case["id"], {}).get("status") == "ok"]
    rng = random.Random(seed)
    flagged = [case for case in ok if results[case["id"]]["alertas"]]
    rest = [case for case in ok if not results[case["id"]]["alertas"]]
    rng.shuffle(flagged)
    rng.shuffle(rest)
    half = amostra // 2
    picked = flagged[:half] + rest[: amostra - min(half, len(flagged))]
    picked += flagged[half: half + amostra - len(picked)]  # completa se faltar sem alerta
    rng.shuffle(picked)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file, delimiter=";")
        writer.writerow(["id", "numero_processo", "tribunal", "tipo_comunicacao", "teor",
                         "causor_status", "causor_dias", "causor_fundamento", *ROTULOS])
        for case in picked:
            causor = results[case["id"]]["causor"]
            writer.writerow([case["id"], case.get("numero_processo"), case.get("tribunal"),
                             case.get("tipo_comunicacao"), html_to_text(case["teor"] or "")[:32000],
                             causor["status"], causor["dias"], causor["fundamento"],
                             *[""] * len(ROTULOS)])


def resumo(results: dict[int, dict]) -> dict:
    ok = [row for row in results.values() if row.get("status") == "ok"]
    vigentes = [row for row in ok if row["causor"]["vigente"]]
    by_reason: dict[str, int] = {}
    for row in vigentes:
        for reason in row["alertas"]:
            by_reason[reason] = by_reason.get(reason, 0) + 1
    tokens = sum((row.get("usage") or {}).get("input_tokens", 0) for row in ok)
    latencies = sorted(row["latencia_ms"] for row in ok)
    return {
        "intimacoes": len(results), "respondidas": len(ok), "falhas": len(results) - len(ok),
        "prazos_vigentes": len(vigentes),
        "vigentes_com_alerta": sum(1 for row in vigentes if row["alertas"]),
        "alertas_por_motivo": by_reason,
        "concordancia_ato": _rate(ok, "ato", ATOS), "concordancia_rito": _rate(ok, "rito", RITO_DESCRICOES),
        "tokens_entrada": tokens, "custo_estimado_usd": round(tokens * 0.042 / 1_000_000, 4),
        "latencia_mediana_ms": latencies[len(latencies) // 2] if latencies else None,
    }


def _rate(rows: list[dict], key: str, valid) -> float | None:
    comparable = [row for row in rows if row["causor"][key] in valid]
    if not comparable:
        return None
    return round(sum(row["jev"][key] == row["causor"][key] for row in comparable) / len(comparable), 3)


def relatorio(out_dir: Path) -> str:
    results = _latest(_read_jsonl(out_dir / "resultados.jsonl"))
    with (out_dir / "rotulos.csv").open(encoding="utf-8-sig", newline="") as file:
        labels = [row for row in csv.DictReader(file, delimiter=";")
                  if any(row[key].strip() for key in ROTULOS[:-1])]
    lines = [f"# Bancada Jev × Causor ({len(labels)} intimações rotuladas)", ""]
    lines += ["| Pergunta | Rotuladas | Causor acerta | Jev acerta |", "|---|---|---|---|"]
    for key, kind in (("prazo_expresso", "bool"), ("multiplos_atos", "bool"), ("ato", "str"), ("rito", "str")):
        causor_hits = jev_hits = total = 0
        for label in labels:
            raw = label[f"r_{key}"].strip().lower()
            row = results.get(int(label["id"]))
            if not raw or not row or row.get("status") != "ok":
                continue
            truth = SIM_NAO.get(raw) if kind == "bool" else raw
            if truth is None:
                continue
            total += 1
            jev = row["jev"][key] >= LIMIAR if kind == "bool" else row["jev"][key]
            causor_hits += row["causor"][key] == truth
            jev_hits += jev == truth
        lines.append(f"| {key} | {total} | {_pct(causor_hits, total)} | {_pct(jev_hits, total)} |")
    wrong = caught = right = false_alarm = 0
    for label in labels:
        verdict = SIM_NAO.get(label["r_prazo_causor_correto"].strip().lower())
        row = results.get(int(label["id"]))
        if verdict is None or not row or not row["causor"]["vigente"]:
            continue
        if verdict:
            right += 1
            false_alarm += bool(row["alertas"])
        else:
            wrong += 1
            caught += bool(row["alertas"])
    lines += ["", "## Prazos que o Causor pôs em vigor sozinho", "",
              f"- Errados segundo o rótulo: {wrong}; a Jev alertou em {_pct(caught, wrong)}.",
              f"- Certos segundo o rótulo: {right}; a Jev alertou à toa em {_pct(false_alarm, right)}.",
              "", "Amostra pequena: isto é diagnóstico, não taxa de acerto."]
    return "\n".join(lines)


def _pct(part: int, total: int) -> str:
    return f"{part}/{total} ({part / total:.0%})" if total else "—"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    exp = sub.add_parser("exportar")
    exp.add_argument("--output", type=Path, default=Path("artifacts/evals/jev/intimacoes.jsonl"))
    exp.add_argument("--limit", type=int, default=1000)
    exp.add_argument("--escritorio", type=int)
    run = sub.add_parser("rodar")
    run.add_argument("--cases", type=Path, default=Path("artifacts/evals/jev/intimacoes.jsonl"))
    run.add_argument("--dir", type=Path, default=Path("artifacts/evals/jev"))
    run.add_argument("--amostra", type=int, default=80)
    run.add_argument("--model", default=DEFAULT_MODEL)
    rep = sub.add_parser("relatorio")
    rep.add_argument("--dir", type=Path, default=Path("artifacts/evals/jev"))
    args = parser.parse_args(argv)
    if args.cmd == "exportar":
        print(f"{exportar(args.output, limit=args.limit, escritorio=args.escritorio)} intimações exportadas para {args.output}")
    elif args.cmd == "rodar":
        summary = rodar(args.cases, args.dir, client=JevClient(model=args.model), amostra=args.amostra)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        print(f"Planilha para rotular: {args.dir / 'rotulos.csv'}")
        print("Rótulos: s/n nas colunas de sim/não (na se não se aplica); "
              f"r_ato em {', '.join(ATOS)}; r_rito em {', '.join(RITO_DESCRICOES)}.")
    else:
        report = relatorio(args.dir)
        (args.dir / "relatorio.md").write_text(report, encoding="utf-8")
        print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
