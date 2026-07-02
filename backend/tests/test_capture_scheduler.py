"""TDD for the capture scheduler (select_due + run_capture_for_oab)."""

from datetime import date, datetime, timedelta, timezone

import pytest
import httpx

from app.capture.djen import ComunicacaoDTO
from app.capture.scheduler import (
    run_capture_for_oab,
    run_capture_for_oab_resilient,
    select_due,
)
from app.prazo_engine.factory import build_calendar
from app.queue.jobs import fail_stale_running_jobs
from app.sor import models


class FakeDjen:
    def __init__(self, items):
        self._items = items
        self.calls = []

    def consultar(self, oab, uf, **kw):
        self.calls.append((oab, uf, kw))
        return self._items


class FakeDatajud:
    def consultar_processo(self, numero_processo, *, tribunal):
        return None


@pytest.fixture
def calendar():
    return build_calendar([2024, 2025])


@pytest.fixture
def escritorio(db_session):
    esc = models.Escritorio(nome="Escritório Teste")
    db_session.add(esc)
    db_session.flush()
    return esc


def _comunicacao(fonte_id="111"):
    return ComunicacaoDTO.from_item(
        {
            "id": fonte_id,
            "numero_processo": "0000001-00.2024.8.26.0100",
            "siglaTribunal": "TJSP",
            "tipoComunicacao": "Intimação",
            "texto": "Intimada para manifestar em 15 dias.",
            "data_disponibilizacao": "2024-09-06",
        }
    )


def test_select_due_includes_never_captured_and_skips_inactive(db_session, escritorio):
    nunca = models.OabMonitorada(escritorio_id=escritorio.id, oab="111", uf="SP")
    inativa = models.OabMonitorada(escritorio_id=escritorio.id, oab="222", uf="SP", ativo=False)
    recente = models.OabMonitorada(
        escritorio_id=escritorio.id, oab="333", uf="SP",
        ultima_captura_em=datetime.now(timezone.utc), intervalo_horas=12,
    )
    db_session.add_all([nunca, inativa, recente])
    db_session.flush()

    due = select_due(db_session)
    oabs = {o.oab for o in due}
    assert "111" in oabs
    assert "222" not in oabs
    assert "333" not in oabs


def test_select_due_includes_overdue(db_session, escritorio):
    velha = models.OabMonitorada(
        escritorio_id=escritorio.id, oab="444", uf="SP",
        ultima_captura_em=datetime.now(timezone.utc) - timedelta(hours=24),
        intervalo_horas=12,
    )
    db_session.add(velha)
    db_session.flush()
    assert {o.oab for o in select_due(db_session)} == {"444"}


def test_run_capture_for_oab_advances_cursor_and_captures(db_session, escritorio, calendar):
    oab = models.OabMonitorada(escritorio_id=escritorio.id, oab="12345", uf="SP")
    db_session.add(oab)
    db_session.flush()

    today = date(2024, 9, 10)
    djen = FakeDjen([_comunicacao()])
    job = run_capture_for_oab(
        db_session, oab, djen=djen, datajud=FakeDatajud(), calendar=calendar, today=today
    )

    assert job.status == "completed"
    assert oab.cursor_data == today
    assert oab.ultima_captura_em is not None
    # janela incremental: data_inicio = today - lookback (3 dias) por não haver cursor
    _, _, kw = djen.calls[0]
    assert kw["data_inicio"] == date(2024, 9, 7)
    assert kw["data_fim"] == today


def test_resilient_capture_accepts_partial_when_djen_unavailable(
    db_session, escritorio, calendar
):
    """DJEN fora: poll_oab preserva o parcial e marca djen_indisponivel=True.
    O scheduler aceita como sucesso (parcial) e nao retenta — o proximo ciclo
    agendado complementa (dedup idempotente)."""
    oab = models.OabMonitorada(escritorio_id=escritorio.id, oab="12345", uf="SP")
    db_session.add(oab)
    db_session.commit()

    class DownDjen(FakeDjen):
        def consultar(self, oab, uf, **kw):
            self.calls.append((oab, uf, kw))
            raise httpx.ConnectError(
                "temporary failure",
                request=httpx.Request("GET", "https://comunica.example"),
            )

    sleeps = []
    djen = DownDjen([])  # DJEN sempre fora
    result = run_capture_for_oab_resilient(
        db_session,
        oab,
        djen=djen,
        datajud=FakeDatajud(),
        calendar=calendar,
        max_attempts=3,
        backoff_seconds=0.5,
        sleeper=sleeps.append,
        today=date(2024, 9, 10),
    )

    assert result.succeeded is True
    assert result.attempts == 1  # nao retenta DJEN; aceita parcial
    assert result.job.status == "completed"
    assert result.job.resultado["djen_indisponivel"] is True
    assert sleeps == []  # nao houve retry externo
    assert db_session.query(models.Intimacao).count() == 0


def test_resilient_capture_records_failure_on_db_operational_error(
    db_session, escritorio, calendar
):
    """Erros de DB (OperationalError) ainda sao transientes e retentados."""
    from sqlalchemy.exc import OperationalError

    oab = models.OabMonitorada(escritorio_id=escritorio.id, oab="12345", uf="SP")
    db_session.add(oab)
    db_session.commit()

    class BoomDjen(FakeDjen):
        def consultar(self, oab, uf, **kw):
            self.calls.append((oab, uf, kw))
            raise OperationalError("statement", {}, Exception("db dead"))

    sleeps = []
    djen = BoomDjen([_comunicacao()])
    result = run_capture_for_oab_resilient(
        db_session,
        oab,
        djen=djen,
        datajud=FakeDatajud(),
        calendar=calendar,
        max_attempts=2,
        backoff_seconds=0.5,
        sleeper=sleeps.append,
    )

    assert result.succeeded is False
    assert result.attempts == 2
    assert result.job.status == "failed"
    assert sleeps == [0.5]


def test_resilient_capture_records_final_failure_without_retrying_domain_error(
    db_session, escritorio, calendar
):
    oab = models.OabMonitorada(escritorio_id=escritorio.id, oab="12345", uf="SP")
    db_session.add(oab)
    db_session.commit()

    class InvalidDjen:
        calls = 0

        def consultar(self, oab, uf, **kw):
            self.calls += 1
            raise ValueError("invalid communication payload")

    djen = InvalidDjen()
    result = run_capture_for_oab_resilient(
        db_session,
        oab,
        djen=djen,
        datajud=FakeDatajud(),
        calendar=calendar,
        max_attempts=3,
        backoff_seconds=0,
    )

    assert result.succeeded is False
    assert result.attempts == 1
    assert result.job.status == "failed"
    assert result.job.payload["tentativas"] == 1
    assert "invalid communication payload" in result.job.erro
    assert djen.calls == 1


def test_fail_stale_running_jobs_preserves_recent_jobs(db_session):
    old = models.JobExecucao(
        tipo="captura_oab",
        status="running",
        updated_at=datetime(2026, 6, 25, 10, 0, tzinfo=timezone.utc),
    )
    recent = models.JobExecucao(
        tipo="captura_oab",
        status="running",
        updated_at=datetime(2026, 6, 25, 11, 45, tzinfo=timezone.utc),
    )
    db_session.add_all([old, recent])
    db_session.flush()

    stale = fail_stale_running_jobs(
        db_session,
        older_than_minutes=60,
        now=datetime(2026, 6, 25, 12, 0, tzinfo=timezone.utc),
    )

    assert stale == [old]
    assert old.status == "failed"
    assert "interrompido" in old.erro
    assert recent.status == "running"


def test_resilient_capture_rejects_zero_attempts(db_session, escritorio, calendar):
    oab = models.OabMonitorada(escritorio_id=escritorio.id, oab="12345", uf="SP")
    db_session.add(oab)
    db_session.flush()

    with pytest.raises(ValueError, match="pelo menos 1"):
        run_capture_for_oab_resilient(
            db_session,
            oab,
            djen=FakeDjen([]),
            datajud=FakeDatajud(),
            calendar=calendar,
            max_attempts=0,
        )


def test_resilient_capture_rejects_negative_backoff(db_session, escritorio, calendar):
    oab = models.OabMonitorada(escritorio_id=escritorio.id, oab="12345", uf="SP")
    db_session.add(oab)
    db_session.flush()

    with pytest.raises(ValueError, match="nao pode ser negativo"):
        run_capture_for_oab_resilient(
            db_session,
            oab,
            djen=FakeDjen([]),
            datajud=FakeDatajud(),
            calendar=calendar,
            backoff_seconds=-1,
        )
