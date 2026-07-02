"""TDD for the captura_oab job executor."""

import pytest

from app.capture.djen import ComunicacaoDTO
from app.prazo_engine.factory import build_calendar
from app.queue.jobs import JobError, create_job, run_capture_oab_job
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


def test_run_capture_job_completes_and_audits(db_session, escritorio, calendar):
    job = create_job(
        db_session,
        tipo="captura_oab",
        entidade="oab_monitorada",
        entidade_id=1,
        payload={"oab": "12345", "uf": "SP", "escritorio_id": escritorio.id},
    )
    db_session.flush()

    djen = FakeDjen([_comunicacao()])
    run_capture_oab_job(
        db_session, job.id, djen=djen, datajud=FakeDatajud(), calendar=calendar
    )

    assert job.status == "completed"
    assert job.resultado["intimacoes_novas"] == 1
    assert job.resultado["prazos_registrados"] == 1
    db_session.flush()  # session uses autoflush=False; surface pending audit rows
    audits = db_session.query(models.AuditLog).all()
    acoes = {a.acao for a in audits}
    assert {"job_iniciado", "job_concluido"} <= acoes
    assert all(a.escritorio_id == escritorio.id for a in audits)


def test_run_capture_job_rejects_wrong_type(db_session, escritorio, calendar):
    job = create_job(db_session, tipo="protocolo_peticao", entidade_id=1)
    db_session.flush()
    with pytest.raises(JobError):
        run_capture_oab_job(
            db_session, job.id, djen=FakeDjen([]), datajud=FakeDatajud(), calendar=calendar
        )


def test_run_capture_job_windowed_splits_range_and_commits_progressively(
    db_session, escritorio, calendar
):
    from app.queue.jobs import _windows
    from datetime import date

    # _windows: cobertura exata de [inicio, fim] em lotes de N dias
    assert list(_windows(date(2024, 1, 1), date(2024, 1, 1), 15)) == [
        (date(2024, 1, 1), date(2024, 1, 1))
    ]
    assert list(_windows(date(2024, 1, 1), date(2024, 1, 31), 15)) == [
        (date(2024, 1, 1), date(2024, 1, 15)),
        (date(2024, 1, 16), date(2024, 1, 30)),
        (date(2024, 1, 31), date(2024, 1, 31)),
    ]

    # uma comunicacao por janela (3 janelas)
    items = [
        _comunicacao(fonte_id="1"),
        _comunicacao(fonte_id="2"),
        _comunicacao(fonte_id="3"),
    ]
    djen = FakeDjen(items)
    job = create_job(
        db_session,
        tipo="captura_oab",
        entidade="escritorio",
        entidade_id=escritorio.id,
        payload={"oab": "12345", "uf": "SP", "escritorio_id": escritorio.id},
    )
    db_session.flush()

    commits: list = []
    run_capture_oab_job(
        db_session,
        job.id,
        djen=djen,
        datajud=FakeDatajud(),
        calendar=calendar,
        data_inicio=date(2024, 1, 1),
        data_fim=date(2024, 1, 31),
        batch_days=15,
        commit_each=lambda s: commits.append(s),
    )

    # 3 janelas -> 3 chamadas ao DJEN, uma por lote
    assert len(djen.calls) == 3
    assert [c[2]["data_inicio"] for c in djen.calls] == [
        date(2024, 1, 1),
        date(2024, 1, 16),
        date(2024, 1, 31),
    ]
    assert job.status == "completed"
    assert job.resultado["intimacoes_novas"] == 3
    assert job.resultado["windows_done"] == 3
    assert job.resultado["windows_total"] == 3
    # commit_each invocado apos cada janela (progressivo)
    assert len(commits) == 3
    assert db_session.query(models.Intimacao).count() == 3


def test_run_capture_job_windowed_is_idempotent_across_windows(db_session, escritorio, calendar):
    from datetime import date

    djen = FakeDjen([_comunicacao(fonte_id="unica")])  # mesma comunicacao em todas as janelas
    job = create_job(
        db_session,
        tipo="captura_oab",
        entidade="escritorio",
        entidade_id=escritorio.id,
        payload={"oab": "12345", "uf": "SP", "escritorio_id": escritorio.id},
    )
    db_session.flush()

    run_capture_oab_job(
        db_session,
        job.id,
        djen=djen,
        datajud=FakeDatajud(),
        calendar=calendar,
        data_inicio=date(2024, 1, 1),
        data_fim=date(2024, 1, 30),
        batch_days=15,
        commit_each=lambda s: None,
    )

    # dedup dentro do normalize: mesma fonte -> 1 intimacao apenas
    assert db_session.query(models.Intimacao).count() == 1
    assert job.resultado["intimacoes_novas"] == 1
