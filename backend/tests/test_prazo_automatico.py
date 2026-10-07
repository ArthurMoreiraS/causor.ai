"""Fluxo automático depois da captura: nenhuma intimação com providência fica sem data.

Incerto ganha data de triagem rotulada; falha é repetida sozinha e, esgotadas
as tentativas, também vira triagem; análise antiga é refeita sem clique.
"""

from datetime import date, datetime, time, timedelta, timezone

import pytest
from sqlalchemy import select

from app.agent.deadline_interpretation import DeadlineInterpretation
from app.prazo_engine import pipeline
from app.alertas.notificacao import notificar_prazos
from app.prazo_engine.pipeline import (
    ANALYSIS_VERSION, MAX_ATTEMPTS, enqueue_analysis, memory, requeue_analyses, run_analysis,
)
from app.queue.jobs import fail_stale_running_jobs, mark_running
from app.sor import models


@pytest.fixture(autouse=True)
def _hoje_fixo(monkeypatch):
    """Datas de triagem dependem de "hoje"; os casos usam a semana de 25/09/2026."""
    monkeypatch.setattr(pipeline, "_today", lambda: date(2026, 9, 28))


def _office(db_session, *, email="adv@example.com"):
    office = models.Escritorio(nome="Automático")
    db_session.add(office)
    db_session.flush()
    if email:
        db_session.add(models.Usuario(escritorio_id=office.id, nome="Adv", email=email,
                                      supabase_user_id=f"sub-{office.id}"))
        db_session.flush()
    return office


def _notice(db_session, office, *, classe="Procedimento Comum Cível", teor="Vistos. Cumpra-se.",
            fonte_id="auto-1", disponibilizacao=date(2026, 9, 25)):
    notice = models.Intimacao(escritorio_id=office.id, fonte="DJEN", fonte_id=fonte_id,
                              teor=teor, tipo_comunicacao="Intimação",
                              data_disponibilizacao=disponibilizacao, payload={"nomeClasse": classe})
    db_session.add(notice)
    db_session.flush()
    return notice


def _start(db_session, notice):
    job = enqueue_analysis(db_session, notice)
    db_session.commit()
    mark_running(db_session, job)
    db_session.commit()
    return job


def _uncertain(ato="outro", rito="comum"):
    def interpret(_text):
        return DeadlineInterpretation(status="incerto", regime="incerto", confianca=0.3,
                                      motivo="Sem duração expressa", ato=ato, rito=rito,
                                      confianca_ato=0.9)
    return interpret


def _broken(_text):
    raise RuntimeError("provedor fora do ar")


def _deadlines(db_session, notice):
    return db_session.scalars(select(models.Prazo).where(models.Prazo.intimacao_id == notice.id)).all()


def test_incerto_civel_ganha_triagem_de_cinco_dias_uteis(db_session):
    notice = _notice(db_session, _office(db_session))
    run_analysis(db_session, _start(db_session, notice), interpreter=_uncertain())

    record = memory(db_session.get(models.Intimacao, notice.id))
    [prazo] = _deadlines(db_session, notice)
    assert record["status"] == "triagem"
    assert record["analise_versao"] == ANALYSIS_VERSION
    assert prazo.revisao_status == "triagem"
    assert (prazo.dias, prazo.dias_uteis) == (5, True)
    # Disponibilizada sexta 25/09: publicação 28/09, contagem 29/09 a 05/10.
    assert prazo.data_fatal == date(2026, 10, 5)
    assert "não identificado" in prazo.descricao
    assert "218" in record["fundamento"]


def test_incerto_criminal_usa_triagem_mais_curta(db_session):
    notice = _notice(db_session, _office(db_session), classe="Ação Penal - Procedimento Ordinário")
    run_analysis(db_session, _start(db_session, notice), interpreter=_uncertain(ato="sentenca"))

    record = memory(db_session.get(models.Intimacao, notice.id))
    [prazo] = _deadlines(db_session, notice)
    assert record["status"] == "triagem" and record["rito"] == "criminal"
    assert prazo.dias == 2
    assert "619" in record["fundamento"]


def test_triagem_ja_vencida_nao_vira_prazo(db_session, monkeypatch):
    """Acervo antigo reanalisado: nada de "vencido" fabricado no radar."""
    monkeypatch.setattr(pipeline, "_today", lambda: date(2026, 10, 7))
    notice = _notice(db_session, _office(db_session))
    run_analysis(db_session, _start(db_session, notice), interpreter=_uncertain())

    record = memory(db_session.get(models.Intimacao, notice.id))
    assert record["status"] == "pendente"
    assert "já passou" in record["motivo"]
    assert _deadlines(db_session, notice) == []


def test_sem_prazo_continua_sem_data(db_session):
    notice = _notice(db_session, _office(db_session), teor="Pauta da sessão de 14/10/2026.")
    run_analysis(db_session, _start(db_session, notice), interpreter=_uncertain(ato="pauta_julgamento"))

    assert memory(db_session.get(models.Intimacao, notice.id))["status"] == "sem_prazo_identificado"
    assert _deadlines(db_session, notice) == []


def test_falha_e_repetida_e_depois_vira_triagem(db_session):
    notice = _notice(db_session, _office(db_session))
    run_analysis(db_session, _start(db_session, notice), interpreter=_broken)
    assert memory(db_session.get(models.Intimacao, notice.id))["tentativas"] == 1

    for attempt in range(2, MAX_ATTEMPTS + 1):
        assert requeue_analyses(db_session) == 1
        db_session.commit()
        job = db_session.scalars(select(models.JobExecucao).where(
            models.JobExecucao.tipo == "analise_prazo", models.JobExecucao.status == "queued")).one()
        mark_running(db_session, job)
        db_session.commit()
        run_analysis(db_session, job, interpreter=_broken)
        record = memory(db_session.get(models.Intimacao, notice.id))
        assert record["tentativas"] == attempt

    assert record["status"] == "triagem"
    assert "indisponível" in record["motivo"]
    assert len(_deadlines(db_session, notice)) == 1
    assert requeue_analyses(db_session) == 0


def test_analise_interrompida_conta_como_tentativa(db_session):
    notice = _notice(db_session, _office(db_session))
    job = _start(db_session, notice)
    job.updated_at = datetime.now(timezone.utc) - timedelta(hours=2)
    db_session.commit()

    fail_stale_running_jobs(db_session, older_than_minutes=30)
    db_session.commit()

    record = memory(db_session.get(models.Intimacao, notice.id))
    assert (record["status"], record["tentativas"]) == ("falha", 1)


def test_reanalisa_versao_antiga_e_intimacao_nunca_analisada(db_session):
    office = _office(db_session)
    old = _notice(db_session, office, fonte_id="antiga")
    old.payload = {**old.payload, "_causor_prazo": {"status": "pendente", "job_id": 1, "analise_versao": 2}}
    never = _notice(db_session, office, fonte_id="nunca")
    current = _notice(db_session, office, fonte_id="atual")
    current.payload = {**current.payload, "_causor_prazo": {
        "status": "sem_prazo_identificado", "job_id": 2, "analise_versao": ANALYSIS_VERSION}}
    human = _notice(db_session, office, fonte_id="humana")
    human.payload = {**human.payload, "_causor_prazo": {"status": "confirmado", "prazo_id": 99}}
    db_session.commit()

    assert requeue_analyses(db_session) == 2
    db_session.commit()
    assert memory(db_session.get(models.Intimacao, old.id))["status"] == "analisando"
    assert memory(db_session.get(models.Intimacao, never.id))["status"] == "analisando"
    assert memory(db_session.get(models.Intimacao, current.id))["status"] == "sem_prazo_identificado"
    assert memory(db_session.get(models.Intimacao, human.id))["status"] == "confirmado"
    assert requeue_analyses(db_session) == 0


class _Sender:
    def __init__(self):
        self.sent = []

    def enviar(self, *, destinos, assunto, corpo):
        self.sent.append({"destinos": destinos, "assunto": assunto, "corpo": corpo})


def test_prazo_novo_e_avisado_uma_vez_mesmo_longe_do_vencimento(db_session):
    office = _office(db_session)
    notice = _notice(db_session, office, disponibilizacao=date.today())
    run_analysis(db_session, _start(db_session, notice), interpreter=_uncertain(ato="sentenca"))
    sender = _Sender()

    notificar_prazos(db_session, sender=sender, escritorio_id=office.id)
    notificar_prazos(db_session, sender=sender, escritorio_id=office.id)

    [mail] = sender.sent
    assert "Apelação" in mail["corpo"]
    assert "calculado automaticamente" in mail["corpo"]
    assert "novo" in mail["assunto"].lower()


def test_triagem_aparece_no_aviso_como_prazo_nao_identificado(db_session):
    office = _office(db_session)
    notice = _notice(db_session, office, disponibilizacao=date.today())
    run_analysis(db_session, _start(db_session, notice), interpreter=_uncertain())
    sender = _Sender()

    notificar_prazos(db_session, sender=sender, escritorio_id=office.id)

    [mail] = sender.sent
    assert "triagem" in mail["corpo"].lower()
    assert "prazo real não identificado" in mail["corpo"]


def test_prazo_antigo_nao_vira_aviso_de_novo(db_session):
    office = _office(db_session)
    prazo = models.Prazo(escritorio_id=office.id, descricao="Antigo", data_inicio=date.today(),
                         dias=15, dias_uteis=True, data_fatal=date.today() + timedelta(days=20))
    db_session.add(prazo)
    db_session.flush()
    prazo.created_at = datetime.now(timezone.utc) - timedelta(days=5)
    db_session.flush()
    sender = _Sender()

    notificar_prazos(db_session, sender=sender, escritorio_id=office.id)

    assert sender.sent == []


def _factory(db_session):
    from sqlalchemy.orm import sessionmaker

    return sessionmaker(db_session.bind, expire_on_commit=False)


def test_ciclo_do_agendador_reanalisa_e_avisa_em_horario_comercial(db_session, monkeypatch):
    from app.capture.service import automation_tick
    from app.settings import settings

    office = _office(db_session)
    notice = _notice(db_session, office, disponibilizacao=date.today())
    db_session.commit()
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.com")
    sender = _Sender()
    now = datetime(2026, 10, 7, 13, 0, tzinfo=timezone.utc)  # 10h em Brasília

    outcome = automation_tick(_factory(db_session), now=now, sender_factory=lambda: sender)

    assert outcome["reanalises"] == 1
    db_session.expire_all()
    assert memory(db_session.get(models.Intimacao, notice.id))["status"] == "analisando"


def test_ciclo_do_agendador_nao_avisa_de_madrugada_nem_sem_smtp(db_session, monkeypatch):
    from app.capture.service import automation_tick
    from app.settings import settings

    office = _office(db_session)
    notice = _notice(db_session, office, disponibilizacao=date.today())
    run_analysis(db_session, _start(db_session, notice), interpreter=_uncertain(ato="sentenca"))
    sender = _Sender()
    night = datetime.combine(date.today(), time(5), tzinfo=timezone.utc)  # 2h em Brasília
    day = datetime.combine(date.today(), time(13), tzinfo=timezone.utc)

    monkeypatch.setattr(settings, "smtp_host", "")
    assert automation_tick(_factory(db_session), now=day, sender_factory=lambda: sender)["avisos"] == 0
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.com")
    assert automation_tick(_factory(db_session), now=night, sender_factory=lambda: sender)["avisos"] == 0
    assert sender.sent == []
    assert automation_tick(_factory(db_session), now=day, sender_factory=lambda: sender)["avisos"] == 1
    assert len(sender.sent) == 1


def test_falha_no_aviso_nao_derruba_o_ciclo_de_captura(tmp_path):
    from app.capture.service import run_loop

    class _Once:
        def __init__(self):
            self.waits = []

        def is_set(self):
            return bool(self.waits)

        def wait(self, interval):
            self.waits.append(interval)

    def broken(_):
        raise RuntimeError("smtp password leaked?")

    heartbeat = tmp_path / "heartbeat"
    run_loop(object(), stop=_Once(), heartbeat=heartbeat, tick=10, enqueue=lambda _: 0, automate=broken)
    assert heartbeat.exists()
