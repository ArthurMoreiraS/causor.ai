from datetime import date

import pytest
from sqlalchemy import select

from app.agent.deadline_interpretation import DeadlineInterpretation
from app.capture.djen import ComunicacaoDTO
from app.capture.poll import poll_oab
from app.prazo_engine.factory import build_calendar
from app.prazo_engine import pipeline
from app.prazo_engine.pipeline import memory, run_analysis
from app.queue.jobs import mark_running
from app.sor import models


@pytest.fixture(autouse=True)
def _hoje_fixo(monkeypatch):
    """Datas de triagem dependem de "hoje"; os casos usam a semana de 25/09/2026."""
    monkeypatch.setattr(pipeline, "_today", lambda: date(2026, 9, 28))


class FakeDjen:
    def __init__(self, item):
        self.item = item

    def consultar(self, **kwargs):
        return [self.item]


class FakeDatajud:
    def consultar_processo(self, *args, **kwargs):
        return None


def _interpret(_text):
    return DeadlineInterpretation(status="prazo", regime="cpc_civel_djen", dias=5,
        unidade="dias_uteis", termo="publicacao_djen", confianca=.96,
        evidencia="manifestar em 5 dias úteis", fundamento="CPC")


def _seed(db_session):
    office = models.Escritorio(nome="Prazo")
    db_session.add(office)
    db_session.flush()
    db_session.add(models.Usuario(escritorio_id=office.id, nome="Adv", email="adv@example.com",
                                  supabase_user_id="adv"))
    db_session.commit()
    item = ComunicacaoDTO.from_item({"id": "notice-1", "numero_processo": "0000001-00.2026.8.26.0100",
        "siglaTribunal": "TJSP", "tipoComunicacao": "Intimação", "nomeClasse": "Procedimento Comum Cível",
        "texto": "Intima-se a parte ré para manifestar em 5 dias úteis.",
        "data_disponibilizacao": "2026-09-25", "_causor_prazo": {"status": "confirmado"}})
    return office, item


def _capture(db_session, office, item):
    return poll_oab(db_session, oab="1", uf="SP", escritorio_id=office.id,
        djen=FakeDjen(item), datajud=FakeDatajud(), calendar=build_calendar(range(2025, 2028)),
        data_inicio=date(2026, 9, 25), data_fim=date(2026, 9, 25), enrich=False)


def test_capture_job_http_confirm_recapture_idempotent(db_session, client):
    office, item = _seed(db_session)
    assert _capture(db_session, office, item).intimacoes_novas == 1
    notice = db_session.scalar(select(models.Intimacao))
    assert memory(notice)["status"] == "analisando"
    assert (notice.payload or {}).get("_causor_prazo") != {"status": "confirmado"}
    job = db_session.scalar(select(models.JobExecucao).where(models.JobExecucao.tipo == "analise_prazo"))
    mark_running(db_session, job)
    db_session.commit()
    run_analysis(db_session, job, interpreter=_interpret)
    prazo = db_session.scalar(select(models.Prazo))
    assert (prazo.data_inicio, prazo.data_fatal) == (date(2026, 9, 28), date(2026, 10, 5))
    assert prazo.revisao_status == "calculado_a_revisar"
    patch = client.patch(f"/prazos/{prazo.id}", json={"descricao": "Manifestação"})
    assert patch.status_code == 200
    assert patch.json()["revisao_status"] == "calculado_a_revisar"
    confirmation = {
        "data_base": "2026-09-28", "dias": 5, "dias_uteis": True,
        "justificativa": "Prazo conferido no teor e no calendário local.", "dias_sem_expediente": []}
    response = client.post(f"/intimacoes/{notice.id}/prazo", json=confirmation)
    assert response.status_code == 200, response.text
    assert response.json()["id"] == prazo.id
    assert response.json()["revisao_status"] == "confirmado"
    retry = client.post(f"/intimacoes/{notice.id}/prazo", json=confirmation)
    assert retry.status_code == 200 and retry.json()["id"] == prazo.id
    assert _capture(db_session, office, item).intimacoes_novas == 0
    assert db_session.query(models.Prazo).count() == 1
    assert db_session.query(models.JobExecucao).filter_by(tipo="analise_prazo").count() == 1


def test_confirmation_keeps_djen_publication_during_recess(db_session, client):
    office, _ = _seed(db_session)
    notice = models.Intimacao(escritorio_id=office.id, fonte="DJEN", fonte_id="recess",
        teor="Manifestar em 1 dia útil.", data_disponibilizacao=date(2026, 12, 21))
    db_session.add(notice)
    db_session.commit()
    response = client.post(f"/intimacoes/{notice.id}/prazo", json={
        "data_base": "2026-12-22", "dias": 1, "dias_uteis": True,
        "justificativa": "Publicação DJEN e duração conferidas pelo advogado.",
        "dias_sem_expediente": []})
    assert response.status_code == 200, response.text
    assert response.json()["data_inicio"] == "2026-12-22"
    assert response.json()["data_fatal"] == "2027-01-21"


def test_legacy_deadline_is_confirmed_in_place_but_multiple_rows_are_ambiguous(db_session, client):
    office, _ = _seed(db_session)
    notice = models.Intimacao(escritorio_id=office.id, fonte="DJEN", fonte_id="legacy",
        teor="Manifestar em 1 dia útil.", data_disponibilizacao=date(2026, 9, 25))
    db_session.add(notice)
    db_session.flush()
    legacy = models.Prazo(escritorio_id=office.id, intimacao_id=notice.id,
        data_inicio=date(2026, 9, 28), dias=15, dias_uteis=True,
        data_fatal=date(2026, 10, 19), cumprido=False)
    db_session.add(legacy)
    db_session.commit()
    body = {"data_base": "2026-09-28", "dias": 1, "dias_uteis": True,
            "justificativa": "Prazo legado conferido pelo advogado no teor.", "dias_sem_expediente": []}
    response = client.post(f"/intimacoes/{notice.id}/prazo", json=body)
    assert response.status_code == 200, response.text
    assert response.json()["id"] == legacy.id
    assert response.json()["data_fatal"] == "2026-09-29"
    assert db_session.query(models.Prazo).count() == 1
    changed = client.post(f"/intimacoes/{notice.id}/prazo", json={**body, "dias": 2})
    assert changed.status_code == 409
    assert db_session.get(models.Prazo, legacy.id).dias == 1

    other = models.Prazo(escritorio_id=office.id, intimacao_id=notice.id,
        data_inicio=date(2026, 9, 28), dias=3, dias_uteis=True,
        data_fatal=date(2026, 10, 1), cumprido=True)
    db_session.add(other)
    db_session.commit()
    assert client.post(f"/intimacoes/{notice.id}/prazo", json=body).status_code == 409


def test_patch_preserves_confirmed_local_holidays_and_count_memory(db_session, client):
    office, _ = _seed(db_session)
    notice = models.Intimacao(escritorio_id=office.id, fonte="DJEN", fonte_id="local",
        teor="Manifestar em 1 dia útil.", data_disponibilizacao=date(2026, 9, 25))
    db_session.add(notice)
    db_session.commit()
    confirmation = client.post(f"/intimacoes/{notice.id}/prazo", json={
        "data_base": "2026-09-28", "dias": 1, "dias_uteis": True,
        "justificativa": "Suspensão local conferida no calendário do tribunal.",
        "dias_sem_expediente": ["2026-09-29"]})
    assert confirmation.status_code == 200, confirmation.text
    prazo_id = confirmation.json()["id"]
    assert confirmation.json()["data_fatal"] == "2026-09-30"
    patch = client.patch(f"/prazos/{prazo_id}", json={"dias": 2})
    assert patch.status_code == 200, patch.text
    assert patch.json()["data_fatal"] == "2026-10-01"
    assert patch.json()["revisao_status"] == "confirmado"
    reviewed = memory(db_session.get(models.Intimacao, notice.id))
    assert reviewed["primeiro_dia"] == "2026-09-30"
    assert reviewed["dias_sem_expediente"] == ["2026-09-29"]
    assert reviewed["data_fatal"] == "2026-10-01"


def test_human_confirmation_during_model_call_discards_late_result(db_session, client):
    office, item = _seed(db_session)
    _capture(db_session, office, item)
    notice = db_session.scalar(select(models.Intimacao))
    job = db_session.scalar(select(models.JobExecucao).where(models.JobExecucao.tipo == "analise_prazo"))
    mark_running(db_session, job)
    db_session.commit()

    def confirm_while_model_runs(text):
        response = client.post(f"/intimacoes/{notice.id}/prazo", json={
            "data_base": "2026-09-28", "dias": 5, "dias_uteis": True,
            "justificativa": "Advogado confirmou antes da resposta do modelo.", "dias_sem_expediente": []})
        assert response.status_code == 200, response.text
        return _interpret(text)

    run_analysis(db_session, job, interpreter=confirm_while_model_runs)
    assert db_session.query(models.Prazo).count() == 1
    assert memory(db_session.get(models.Intimacao, notice.id))["status"] == "confirmado"
    assert db_session.get(models.JobExecucao, job.id).resultado["status"] == "obsoleto"


def test_provider_failure_can_retry_without_recapture(db_session, client):
    office, item = _seed(db_session)
    _capture(db_session, office, item)
    notice = db_session.scalar(select(models.Intimacao))
    job = db_session.scalar(select(models.JobExecucao).where(models.JobExecucao.tipo == "analise_prazo"))
    mark_running(db_session, job)
    db_session.commit()

    def unavailable(_text):
        raise TimeoutError("simulated provider timeout")

    run_analysis(db_session, job, interpreter=unavailable)
    assert memory(db_session.get(models.Intimacao, notice.id))["status"] == "falha"
    assert db_session.query(models.Prazo).count() == 0
    retry = client.post(f"/intimacoes/{notice.id}/analisar-prazo")
    assert retry.status_code == 200
    next_job = db_session.get(models.JobExecucao, retry.json()["job_id"])
    assert next_job.id != job.id
    mark_running(db_session, next_job)
    db_session.commit()
    run_analysis(db_session, next_job, interpreter=_interpret)
    assert db_session.query(models.Prazo).count() == 1
    assert memory(db_session.get(models.Intimacao, notice.id))["status"] == "calculado_a_revisar"


def test_changed_source_discards_late_model_result(db_session):
    office, item = _seed(db_session)
    _capture(db_session, office, item)
    notice = db_session.scalar(select(models.Intimacao))
    job = db_session.scalar(select(models.JobExecucao).where(models.JobExecucao.tipo == "analise_prazo"))
    mark_running(db_session, job)
    db_session.commit()

    def change_source(text):
        notice.teor = text + " Informação retificada."
        db_session.commit()
        return _interpret(text)

    run_analysis(db_session, job, interpreter=change_source)
    assert db_session.get(models.JobExecucao, job.id).resultado["status"] == "obsoleto"
    assert memory(db_session.get(models.Intimacao, notice.id))["status"] == "falha"
    assert db_session.query(models.Prazo).count() == 0


def test_official_raw_class_is_available_before_datajud_enrichment(db_session, monkeypatch):
    from app.prazo_engine import pipeline

    office, item = _seed(db_session)
    _capture(db_session, office, item)
    job = db_session.scalar(select(models.JobExecucao).where(models.JobExecucao.tipo == "analise_prazo"))
    mark_running(db_session, job)
    db_session.commit()
    seen = {}

    def interpret(text, *, context):
        seen.update(context)
        return _interpret(text)

    monkeypatch.setattr(pipeline, "interpret_deadline", interpret)
    run_analysis(db_session, job, interpreter=interpret)
    assert seen["fonte"] == "DJEN"
    assert seen["classe"] == "Procedimento Comum Cível"
    assert db_session.query(models.Prazo).count() == 1


def test_statutory_rule_calculates_and_records_proof_without_replacing_human_review(db_session, client):
    office, _ = _seed(db_session)
    text = ("Intime-se o apelado para apresentar contrarrazões de apelação. "
            "Conforme art. 1.010, § 1º, do CPC.")
    notice = models.Intimacao(escritorio_id=office.id, fonte="DJEN", fonte_id="legal-1",
        teor=text, data_disponibilizacao=date(2026, 9, 25))
    db_session.add(notice)
    db_session.flush()
    from app.prazo_engine.pipeline import enqueue_analysis

    job = enqueue_analysis(db_session, notice)
    db_session.commit()
    mark_running(db_session, job)
    db_session.commit()

    def interpret(_text):
        return DeadlineInterpretation(status="prazo", regime="cpc_civel_djen",
            unidade="dias_uteis", termo="publicacao_djen", confianca=.97,
            origem_duracao="regra_legal", regra_id="cpc_1010_1",
            comando=text.split(" Conforme")[0], citacao_normativa=text.split("Conforme ")[-1])

    run_analysis(db_session, job, interpreter=interpret)
    prazo = db_session.scalar(select(models.Prazo).where(models.Prazo.intimacao_id == notice.id))
    assert prazo.dias == 15 and prazo.revisao_status == "calculado_a_revisar"
    proof = memory(db_session.get(models.Intimacao, notice.id))
    assert proof["origem_duracao"] == "regra_legal"
    assert proof["regra_id"] == "cpc_1010_1"
    assert proof["regra_versao"] and proof["fonte_normativa"].startswith("https://www.planalto.gov.br/")
    assert proof["comando_literal"] in text and proof["citacao_normativa_literal"] in text
    assert proof["evidencia"] == proof["comando_literal"]
    assert proof["fundamento"] == "CPC art. 1010, § 1; 15 dias úteis"
    assert "feriados_e_suspensoes_locais_nao_homologados" in proof["calendario"]
    assert enqueue_analysis(db_session, notice) is None
    assert db_session.query(models.Prazo).filter_by(intimacao_id=notice.id).count() == 1
    confirmation = client.post(f"/intimacoes/{notice.id}/prazo", json={
        "data_base": "2026-09-28", "dias": 15, "dias_uteis": True,
        "justificativa": "Advogado conferiu a fonte e o calendário local.",
        "dias_sem_expediente": []})
    assert confirmation.status_code == 200, confirmation.text
    assert confirmation.json()["id"] == prazo.id
    assert enqueue_analysis(db_session, notice) is None
    assert db_session.query(models.Prazo).filter_by(intimacao_id=notice.id).count() == 1


@pytest.mark.parametrize("special_source", ["raw_class", "process_organ"])
def test_official_juizado_metadata_blocks_even_supported_notice_text(db_session, special_source):
    office, _ = _seed(db_session)
    text = ("Intime-se o apelado para apresentar contrarrazões de apelação. "
            "Conforme art. 1.010, § 1º, do CPC.")
    process = None
    if special_source == "process_organ":
        process = models.Processo(escritorio_id=office.id, numero="0000002-00.2026.8.26.0100",
            classe="Procedimento Comum Cível", orgao_julgador="Juizado Especial Cível")
        db_session.add(process)
        db_session.flush()
    notice = models.Intimacao(escritorio_id=office.id, fonte="DJEN",
        fonte_id=f"special-{special_source}", processo_id=process.id if process else None,
        teor=text, data_disponibilizacao=date(2026, 9, 25),
        payload={"nomeClasse": "Procedimento do Juizado Especial Cível"}
        if special_source == "raw_class" else {})
    db_session.add(notice)
    db_session.flush()
    from app.prazo_engine.pipeline import enqueue_analysis

    job = enqueue_analysis(db_session, notice)
    db_session.commit()
    mark_running(db_session, job)
    db_session.commit()

    def interpret(_text):
        return DeadlineInterpretation(status="prazo", regime="cpc_civel_djen",
            unidade="dias_uteis", termo="publicacao_djen", confianca=.97,
            origem_duracao="regra_legal", regra_id="cpc_1010_1",
            comando=text.split(" Conforme")[0], citacao_normativa=text.split("Conforme ")[-1])

    run_analysis(db_session, job, interpreter=interpret)
    record = memory(db_session.get(models.Intimacao, notice.id))
    # O regime especial bloqueia o cálculo pelo texto; resta só a data de triagem.
    assert record["status"] == "triagem"
    assert "regime especial" in record["motivo"]
    [prazo] = db_session.query(models.Prazo).filter_by(intimacao_id=notice.id).all()
    assert prazo.dias == 5 and "não identificado" in prazo.descricao
