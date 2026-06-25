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
