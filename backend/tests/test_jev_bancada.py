import csv
import json

import pytest

from app.agent import jev_bancada
from app.agent.jev import JevClient, JevError
from app.capture.text import html_to_text


def _answers(*, expresso=0.98, multiplos=0.02, providencia=0.97, ato="intimacao_manifestacao", rito="comum"):
    return {"model": "jev-1.13.0", "usage": {"input_tokens": 600, "output_tokens": 100}, "answers": {
        "prazo_expresso": {"type": "noul", "noul": expresso},
        "multiplos_atos": {"type": "noul", "noul": multiplos},
        "exige_providencia": {"type": "noul", "noul": providencia},
        "ato": {"type": "choice", "choice": ato, "confidence": 0.9, "probabilities": {}},
        "rito": {"type": "choice", "choice": rito, "confidence": 0.9, "probabilities": {}},
    }}


def _case(case_id, *, status="calculado_a_revisar", origem="judicial_expressa", ato="intimacao_manifestacao"):
    return {"id": case_id, "numero_processo": "0001234-56.2026.8.26.0100", "tribunal": "TJSP",
            "tipo_comunicacao": "Intimação", "teor": f"Intime-se a autora em 15 dias. ({case_id})",
            "analise": {"status": status, "prazo_id": case_id, "dias": 15, "origem_duracao": origem,
                        "fundamento": "Prazo judicial", "ato": ato, "rito": "comum", "motivo": None}}


class FakeJev:
    def __init__(self, replies):
        self.replies = replies
        self.states = []

    def ask(self, state, questions):
        self.states.append(state)
        reply = self.replies[len(self.states) - 1]
        if isinstance(reply, Exception):
            raise reply
        return reply


def test_client_sends_bearer_and_never_echoes_key(httpx_mock):
    httpx_mock.add_response(url="https://api.typesafe.ai/v1/systemone", json=_answers())
    client = JevClient(api_key="segredo-123")
    assert client.ask("estado", jev_bancada.PERGUNTAS)["answers"]["ato"]["choice"] == "intimacao_manifestacao"
    request = httpx_mock.get_request()
    assert request.headers["Authorization"] == "Bearer segredo-123"
    assert json.loads(request.content)["model"] == "jev-latest"

    httpx_mock.add_response(status_code=401, json={"detail": "segredo-123 inválida"})
    with pytest.raises(JevError) as error:
        client.ask("estado", {})
    assert "segredo-123" not in str(error.value)


def test_client_retries_transient_errors(httpx_mock):
    httpx_mock.add_response(status_code=503)
    httpx_mock.add_response(json=_answers())
    client = JevClient(api_key="k", backoff_seconds=0)
    assert client.ask("estado", {})["model"] == "jev-1.13.0"


def test_client_requires_key(monkeypatch):
    monkeypatch.delenv("CAUSOR_JEV_API_KEY", raising=False)
    with pytest.raises(JevError):
        JevClient()


def test_alerts_only_make_in_force_deadlines_more_cautious():
    causor = jev_bancada.causor_view(_case(1)["analise"])
    jev = jev_bancada.jev_view(_answers()["answers"])
    assert jev_bancada.alertas(causor, jev) == []
    jev = jev_bancada.jev_view(_answers(expresso=0.1, multiplos=0.9, ato="sentenca")["answers"])
    assert jev_bancada.alertas(causor, jev) == ["multiplos_atos", "sem_prazo_expresso", "ato_divergente"]
    triagem = jev_bancada.causor_view(_case(2, status="triagem")["analise"])
    assert jev_bancada.alertas(triagem, jev) == []
    sentenca = jev_bancada.causor_view(_case(3, origem="regra_por_ato", ato="sentenca")["analise"])
    no_order = jev_bancada.jev_view(_answers(expresso=0.06, providencia=0.42, ato="sentenca")["answers"])
    assert jev_bancada.alertas(sentenca, no_order) == []
    written = jev_bancada.jev_view(_answers(expresso=0.98, ato="sentenca")["answers"])
    assert jev_bancada.alertas(sentenca, written) == ["prazo_escrito_no_teor"]


def test_run_is_resumable_and_label_sheet_is_blind(tmp_path):
    cases = tmp_path / "intimacoes.jsonl"
    cases.write_text("\n".join(json.dumps(_case(i)) for i in (1, 2, 3)), encoding="utf-8")
    first = FakeJev([_answers(), JevError("Jev indisponível: HTTP 503"), _answers(multiplos=0.9)])
    summary = jev_bancada.rodar(cases, tmp_path, client=first, amostra=10)
    assert summary["respondidas"] == 2 and summary["falhas"] == 1
    assert summary["vigentes_com_alerta"] == 1
    assert "Tribunal: TJSP" in first.states[0]

    (tmp_path / "rotulos.csv").unlink()
    second = FakeJev([_answers()])
    summary = jev_bancada.rodar(cases, tmp_path, client=second, amostra=10)
    assert len(second.states) == 1  # só a que falhou
    assert summary["respondidas"] == 3 and summary["falhas"] == 0

    with (tmp_path / "rotulos.csv").open(encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file, delimiter=";"))
    assert sorted(int(row["id"]) for row in rows) == [1, 2, 3]
    assert not any(column.startswith("jev") for column in rows[0])


def test_run_skips_notices_still_being_analysed(tmp_path):
    cases = tmp_path / "intimacoes.jsonl"
    pending = {**_case(2), "analise": {"status": "analisando"}}
    cases.write_text("\n".join(json.dumps(c) for c in (_case(1), pending, {**_case(3), "analise": None})),
                     encoding="utf-8")
    fake = FakeJev([_answers()])
    summary = jev_bancada.rodar(cases, tmp_path, client=fake, amostra=10)
    assert len(fake.states) == 1 and summary["respondidas"] == 1


def test_label_sheet_text_is_readable():
    teor = "<html><style>x{}</style><b>Apela&ccedil;&atilde;o</b><br>Intime-se&nbsp;a  autora.</html>"
    assert html_to_text(teor) == "Apelação\nIntime-se a autora."


def test_label_sheet_is_never_overwritten(tmp_path):
    cases = tmp_path / "intimacoes.jsonl"
    cases.write_text(json.dumps(_case(1)), encoding="utf-8")
    (tmp_path / "rotulos.csv").write_text("já rotulado", encoding="utf-8")
    jev_bancada.rodar(cases, tmp_path, client=FakeJev([_answers()]), amostra=10)
    assert (tmp_path / "rotulos.csv").read_text(encoding="utf-8") == "já rotulado"


def test_report_compares_causor_and_jev_against_labels(tmp_path):
    cases = tmp_path / "intimacoes.jsonl"
    cases.write_text("\n".join(json.dumps(_case(i)) for i in (1, 2)), encoding="utf-8")
    jev_bancada.rodar(cases, tmp_path, client=FakeJev([_answers(multiplos=0.9), _answers()]), amostra=10)
    sheet = tmp_path / "rotulos.csv"
    with sheet.open(encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file, delimiter=";"))
    for row in rows:
        errado = row["id"] == "1"
        row.update(r_prazo_causor_correto="n" if errado else "s", r_multiplos_atos="s" if errado else "n",
                   r_prazo_expresso="s", r_ato="intimacao_manifestacao", r_rito="comum")
    with sheet.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]), delimiter=";")
        writer.writeheader()
        writer.writerows(rows)

    report = jev_bancada.relatorio(tmp_path)
    assert "| multiplos_atos | 2 | 1/2 (50%) | 2/2 (100%) |" in report
    assert "Errados segundo o rótulo: 1; a Jev alertou em 1/1 (100%)." in report
    assert "alertou à toa em 0/1 (0%)." in report
