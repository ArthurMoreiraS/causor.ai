"""Sugestão de prazo pelo tipo de ato quando o teor não traz duração expressa."""

from datetime import date

from sqlalchemy import select

from app.agent.deadline_interpretation import MAX_TEXT, DeadlineInterpretation, text_for_model
from app.prazo_engine.pipeline import enqueue_analysis, memory, run_analysis
from app.queue.jobs import mark_running
from app.sor import models


def _notice(db_session, *, classe="Procedimento Comum Cível", teor="Ante o exposto, JULGO IMPROCEDENTE o pedido."):
    office = models.Escritorio(nome="Prazo por ato")
    db_session.add(office)
    db_session.flush()
    notice = models.Intimacao(escritorio_id=office.id, fonte="DJEN", fonte_id=f"ato-{classe}",
                              teor=teor, tipo_comunicacao="Intimação",
                              data_disponibilizacao=date(2026, 9, 25), payload={"nomeClasse": classe})
    db_session.add(notice)
    db_session.flush()
    job = enqueue_analysis(db_session, notice)
    db_session.commit()
    mark_running(db_session, job)
    db_session.commit()
    return notice, job


def _reading(ato, rito="comum", confianca_ato=0.9):
    def interpret(_text):
        return DeadlineInterpretation(status="incerto", regime="incerto", confianca=0.3,
                                      motivo="Sem duração expressa", ato=ato, rito=rito,
                                      confianca_ato=confianca_ato)
    return interpret


def _deadlines(db_session, notice):
    return db_session.scalars(select(models.Prazo).where(models.Prazo.intimacao_id == notice.id)).all()


def test_sentenca_sugere_apelacao_e_embargos_com_datas(db_session):
    notice, job = _notice(db_session)

    run_analysis(db_session, job, interpreter=_reading("sentenca"))

    record = memory(db_session.get(models.Intimacao, notice.id))
    [prazo] = _deadlines(db_session, notice)
    assert record["status"] == "calculado_a_revisar"
    assert record["origem_duracao"] == "regra_por_ato"
    assert (prazo.descricao, prazo.dias, prazo.dias_uteis) == ("Apelação", 15, True)
    assert prazo.revisao_status == "calculado_a_revisar"
    assert record["data_fatal"] == prazo.data_fatal.isoformat()
    assert "CPC, arts. 1.003, § 5º, e 1.009" in record["fundamento"]
    nomes = [alt["ato_cabivel"] for alt in record["alternativas"]]
    assert nomes == ["Apelação", "Embargos de declaração"]
    embargos = record["alternativas"][1]
    assert embargos["dias"] == 5 and embargos["data_fatal"] < record["data_fatal"]
    assert "parte representada" in record["motivo"]


def test_pauta_de_julgamento_fica_sem_prazo_explicado(db_session):
    notice, job = _notice(db_session, teor="Pauta da sessão de julgamento de 14/10/2026.")

    run_analysis(db_session, job, interpreter=_reading("pauta_julgamento"))

    record = memory(db_session.get(models.Intimacao, notice.id))
    assert record["status"] == "sem_prazo_identificado"
    assert "pauta" in record["motivo"]
    assert _deadlines(db_session, notice) == []


def test_baixa_confianca_no_ato_nao_cria_prazo(db_session):
    notice, job = _notice(db_session)

    run_analysis(db_session, job, interpreter=_reading("sentenca", confianca_ato=0.4))

    assert memory(db_session.get(models.Intimacao, notice.id))["status"] == "pendente"
    assert _deadlines(db_session, notice) == []


def test_rito_criminal_nunca_recebe_sugestao(db_session):
    notice, job = _notice(db_session, classe="Ação Penal - Procedimento Ordinário")

    run_analysis(db_session, job, interpreter=_reading("sentenca", rito="comum"))

    record = memory(db_session.get(models.Intimacao, notice.id))
    assert record["status"] == "pendente" and record["rito"] == "criminal"
    assert "criminal" in record["motivo"]
    assert _deadlines(db_session, notice) == []


def test_metadado_de_juizado_prevalece_sobre_a_leitura_do_modelo(db_session):
    notice, job = _notice(db_session, classe="Procedimento do Juizado Especial Cível")

    run_analysis(db_session, job, interpreter=_reading("sentenca", rito="comum"))

    [prazo] = _deadlines(db_session, notice)
    assert (prazo.descricao, prazo.dias) == ("Recurso inominado", 10)
    assert memory(db_session.get(models.Intimacao, notice.id))["rito"] == "juizado"


def test_prazo_expresso_continua_tendo_prioridade_sobre_o_ato(db_session):
    teor = "Intime-se a parte ré para manifestar em 10 dias úteis sobre o laudo."
    notice, job = _notice(db_session, teor=teor)

    def interpret(_text):
        return DeadlineInterpretation(status="prazo", regime="cpc_civel_djen", dias=10, unidade="dias_uteis",
                                      termo="publicacao_djen", confianca=0.95, evidencia="manifestar em 10 dias úteis",
                                      ato="intimacao_manifestacao", rito="comum", confianca_ato=0.9)

    run_analysis(db_session, job, interpreter=interpret)

    [prazo] = _deadlines(db_session, notice)
    assert prazo.dias == 10
    assert memory(db_session.get(models.Intimacao, notice.id)).get("origem_duracao") == "judicial_expressa"


def test_teor_longo_e_analisado_pelo_inicio_e_pelo_dispositivo():
    texto = "INICIO " + "x" * (MAX_TEXT * 2) + " DISPOSITIVO: JULGO PROCEDENTE"
    reduzido = text_for_model(texto)
    assert len(reduzido) < MAX_TEXT + 100
    assert reduzido.startswith("INICIO") and reduzido.endswith("JULGO PROCEDENTE")
    assert text_for_model("curto") == "curto"


def test_analise_antiga_sem_prazo_pode_ser_refeita_mas_a_atual_nao(db_session):
    from app.prazo_engine.pipeline import set_memory

    notice, job = _notice(db_session)
    run_analysis(db_session, job, interpreter=_reading("pauta_julgamento"))
    notice = db_session.get(models.Intimacao, notice.id)
    assert enqueue_analysis(db_session, notice) is None  # versão atual: terminal

    old = {k: v for k, v in memory(notice).items() if k != "analise_versao"}
    set_memory(notice, {**old, "status": "pendente"})
    db_session.commit()
    assert enqueue_analysis(db_session, notice) is not None

    other, _ = _notice(db_session, classe="Outra classe")
    set_memory(other, {"status": "pendente", "motivo": "Prazo anterior exige conferência de origem"})
    db_session.commit()
    assert enqueue_analysis(db_session, other) is None  # marcação humana/legada sem job


def test_confirmacao_com_alternativa_escolhida_renomeia_o_prazo(db_session, client):
    notice, job = _notice(db_session)
    db_session.add(models.Usuario(escritorio_id=notice.escritorio_id, nome="Adv", email="adv@example.invalid"))
    db_session.commit()
    run_analysis(db_session, job, interpreter=_reading("sentenca"))
    record = memory(db_session.get(models.Intimacao, notice.id))
    embargos = record["alternativas"][1]

    response = client.post(f"/intimacoes/{notice.id}/prazo", json={
        "data_base": record["publicacao"], "dias": embargos["dias"], "dias_uteis": True,
        "justificativa": f"{embargos['ato_cabivel']}: {embargos['fundamento']}",
        "dias_sem_expediente": [], "descricao": embargos["ato_cabivel"]})

    assert response.status_code == 200, response.text
    assert response.json()["descricao"] == "Embargos de declaração"
    assert response.json()["data_fatal"] == embargos["data_fatal"]
    assert len(_deadlines(db_session, notice)) == 1
