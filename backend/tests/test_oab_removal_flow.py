from datetime import date

import pytest
from sqlalchemy import select, text

from app.sor import models
from tests.test_oab_cleanup import tracked_case


@pytest.fixture(autouse=True)
def foreign_keys(db_session):
    if db_session.bind.dialect.name == "sqlite":
        db_session.commit()
        db_session.execute(text("PRAGMA foreign_keys=ON"))


def remove(client, oab="12345"):
    return client.post("/capturas/oab/remover-dados", json={"oab": oab, "uf": "SP"})


def test_cleanup_after_registration_was_already_removed(client, db_session, seeded):
    oab, notice = tracked_case(db_session, seeded)
    notice_id, process_id = notice.id, seeded.id
    db_session.delete(oab)
    db_session.commit()
    response = remove(client)
    assert response.status_code == 200, response.text
    assert response.json()["oab_id"] is None
    assert response.json()["removidos"]["intimacoes"] == 1
    assert db_session.get(models.Intimacao, notice_id) is None
    assert db_session.get(models.Processo, process_id) is None
    assert remove(client).json()["removidos"]["intimacoes"] == 0


@pytest.mark.parametrize("kind", ["work", "document", "draft", "confirmed"])
def test_cleanup_preserves_authored_case(client, db_session, seeded, kind):
    oab, notice = tracked_case(db_session, seeded)
    if kind == "work":
        db_session.add(models.TrabalhoJuridico(escritorio_id=seeded.escritorio_id,
            processo_id=seeded.id, intimacao_id=notice.id, providencia="Preparar manifestação"))
    elif kind == "document":
        db_session.add(models.Documento(escritorio_id=seeded.escritorio_id,
                                      processo_id=seeded.id, nome="Documento enviado"))
    elif kind == "draft":
        db_session.add(models.Peticao(escritorio_id=seeded.escritorio_id, processo_id=seeded.id))
    else:
        notice.payload = {**notice.payload, "_causor_prazo": {"status": "confirmado"}}
    db_session.commit()
    response = remove(client)
    assert response.status_code == 200, response.text
    assert response.json()["removidos"]["intimacoes_preservadas"] == 1
    assert db_session.get(models.Intimacao, notice.id) is not None
    assert db_session.get(models.Processo, seeded.id) is not None
    assert db_session.get(models.OabMonitorada, oab.id) is None


def test_same_notice_shared_with_active_oab_and_other_tenant_are_preserved(client, db_session, seeded):
    _, notice = tracked_case(db_session, seeded)
    notice.payload = {**notice.payload, "_causor_oabs": [{"oab": "99999", "uf": "SP"}]}
    other = models.Escritorio(nome="Outro")
    db_session.add(other)
    db_session.flush()
    private = models.Intimacao(escritorio_id=other.id, fonte="DJEN", fonte_id="private",
                              payload=notice.payload)
    db_session.add_all([private, models.OabMonitorada(escritorio_id=seeded.escritorio_id,
                                                    oab="99999", uf="SP", ativo=True)])
    db_session.commit()
    assert remove(client).json()["removidos"]["intimacoes"] == 0
    assert db_session.get(models.Intimacao, notice.id) is not None
    assert db_session.get(models.Intimacao, private.id) is not None


def test_removal_between_windows_prevents_late_capture_and_replay(client, db_session, seeded):
    from app.capture.djen import ComunicacaoDTO
    from app.prazo_engine.factory import build_calendar
    from app.queue.jobs import JobError, run_capture_oab_job

    job = client.post("/jobs/capture/oab", json={"oab": "12345", "uf": "SP",
        "request_id": "before-removal", "data_inicio": "2026-09-28", "data_fim": "2026-09-29"}).json()
    calls = []

    class Djen:
        def consultar(self, **kwargs):
            calls.append(kwargs)
            return [ComunicacaoDTO.from_item({"id": "window-1", "numero_processo": seeded.numero,
                "texto": "Intimação de teste", "data_disponibilizacao": "2026-09-28"})]

    def commit_and_remove(session):
        session.commit()
        response = remove(client)
        assert response.status_code == 200, response.text

    with pytest.raises(JobError, match="cancelada"):
        run_capture_oab_job(db_session, job["id"], djen=Djen(), datajud=None,
            calendar=build_calendar([2026]), enrich=False, batch_days=1,
            data_inicio=date(2026, 9, 28), data_fim=date(2026, 9, 29), commit_each=commit_and_remove)
    db_session.rollback()
    assert len(calls) == 1
    assert db_session.scalar(select(models.Intimacao).where(models.Intimacao.fonte_id == "window-1")) is None
    replay = client.post("/jobs/capture/oab", json={"oab": "12345", "uf": "SP", "request_id": "before-removal"})
    assert replay.json()["payload"]["removida"] is True
    assert replay.json()["status"] == "failed"
    assert db_session.query(models.OabMonitorada).count() == 0


def test_removal_does_not_confuse_oab_letter_suffixes(client, db_session, seeded):
    _, notice = tracked_case(db_session, seeded)
    notice.payload = {"destinatarioadvogados": [{"advogado": {"numero_oab": "12345A", "uf_oab": "SP"}}]}
    db_session.commit()
    assert remove(client, "12345B").json()["removidos"]["intimacoes"] == 0
    assert db_session.get(models.Intimacao, notice.id) is not None
