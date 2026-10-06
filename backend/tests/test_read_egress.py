"""Read APIs must not download raw court payloads just to count or poll."""
from datetime import date, timedelta
from zoneinfo import ZoneInfo
from datetime import datetime
import re

from sqlalchemy import event, select
import pytest

from app.sor import models


def test_notice_lists_keep_text_and_analysis_without_raw_payload(client, db_session, seeded):
    notice = db_session.scalar(select(models.Intimacao))
    analysis = {"status": "analisando", "job_id": 12}
    notice.payload = {"texto": "RAW_DJEN_SENTINEL" * 10000, "_causor_prazo": analysis}
    db_session.flush()
    statements = []

    def capture(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(db_session.get_bind(), "before_cursor_execute", capture)
    try:
        for path in ("/intimacoes", "/review/queue"):
            response = client.get(path)
            assert response.status_code == 200
            item = response.json()[0]
            if path == "/review/queue":
                item = item["intimacao"]
            assert item["teor"] == notice.teor
            assert item["prazo_analise"] == analysis
            assert "RAW_DJEN_SENTINEL" not in response.text
    finally:
        event.remove(db_session.get_bind(), "before_cursor_execute", capture)
    # A projected JSON key is allowed; selecting the entire JSON column is not.
    for statement in statements:
        if statement.startswith("SELECT"):
            projection = statement.split("FROM")[0]
            assert not re.search(r"(?:^SELECT |,\s*)intimacao(?:_\d+)?\.payload(?:,|\s+AS)", projection)
    assert notice.payload["texto"].startswith("RAW_DJEN_SENTINEL")


def test_compact_analysis_status_is_scoped_and_validated(client, db_session, seeded):
    notice = db_session.scalar(select(models.Intimacao))
    notice.payload = {"texto": "raw-secret", "_causor_prazo": {"status": "analisando", "job_id": 5}}
    other = models.Escritorio(nome="Outro")
    db_session.add(other)
    db_session.flush()
    foreign = models.Intimacao(escritorio_id=other.id, fonte="DJEN", fonte_id="foreign", teor="private")
    db_session.add(foreign)
    db_session.flush()
    response = client.get("/intimacoes/analise-status", params=[("ids", notice.id), ("ids", foreign.id)])
    assert response.status_code == 200
    assert response.json() == [{"id": notice.id, "prazo_analise": notice.prazo_analise}]
    assert "teor" not in response.text and "raw-secret" not in response.text
    assert client.get("/intimacoes/analise-status").status_code == 422
    assert client.get("/intimacoes/analise-status", params=[("ids", 1)] * 201).status_code == 422


def test_metrics_count_in_database_and_keep_deadline_review_semantics(client, db_session, seeded):
    notice = db_session.scalar(select(models.Intimacao))
    deadline = db_session.scalar(select(models.Prazo).where(models.Prazo.cumprido.is_(False)))
    today = datetime.now(ZoneInfo("America/Sao_Paulo")).date()
    deadline.data_fatal = today - timedelta(days=1)
    notice.payload = {"_causor_prazo": {"status": "confirmado", "prazo_id": deadline.id}, "texto": "raw" * 10000}
    other = models.Escritorio(nome="Outro")
    db_session.add(other)
    db_session.flush()
    db_session.add(models.Prazo(escritorio_id=other.id, data_inicio=date(2026, 9, 1), dias=5,
                               data_fatal=today, cumprido=False))
    db_session.add(models.Peticao(processo_id=seeded.id, escritorio_id=seeded.escritorio_id, status="aprovada"))
    db_session.flush()
    statements = []

    def capture(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(db_session.get_bind(), "before_cursor_execute", capture)
    try:
        values = {item["key"]: item["value"] for item in client.get("/dashboard/operational").json()["metrics"]}
    finally:
        event.remove(db_session.get_bind(), "before_cursor_execute", capture)
    assert values == {"processos": 1, "intimacoes": 1, "prazos": 1, "prazos_a_revisar": 0,
                      "risco": 1, "vencidos": 1, "minutas": 0, "aprovadas": 1}
    assert all("intimacao.teor" not in sql and "peticao.conteudo" not in sql for sql in statements)
    # A stale memory pointer cannot mark this deadline as confirmed.
    notice.payload = {"_causor_prazo": {"status": "confirmado", "prazo_id": "invalid"}}
    db_session.flush()
    values = {item["key"]: item["value"] for item in client.get("/dashboard/operational").json()["metrics"]}
    assert values["prazos_a_revisar"] == 1
    assert values["risco"] == values["vencidos"] == 0


@pytest.mark.parametrize("days,risk,overdue", [(-1, 1, 1), (0, 1, 0), (3, 1, 0), (4, 0, 0)])
def test_confirmed_deadline_risk_boundaries(client, db_session, seeded, days, risk, overdue):
    notice = db_session.scalar(select(models.Intimacao))
    deadline = db_session.scalar(select(models.Prazo).where(models.Prazo.cumprido.is_(False)))
    deadline.data_fatal = datetime.now(ZoneInfo("America/Sao_Paulo")).date() + timedelta(days=days)
    notice.payload = {"_causor_prazo": {"status": "confirmado", "prazo_id": deadline.id}}
    db_session.flush()
    values = {item["key"]: item["value"] for item in client.get("/dashboard/operational").json()["metrics"]}
    assert values["risco"] == risk
    assert values["vencidos"] == overdue
    assert values["prazos"] == 1
