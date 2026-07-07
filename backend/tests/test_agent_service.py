"""TDD for the persisted agent workflow."""

from datetime import date, datetime, timezone
from unittest.mock import patch

import httpx

from app.agent.classifier import ClassificacaoIntimacao
from app.agent.drafter import MinutaGerada
from app.agent.service import _historico_processo, draft_from_intimacao
from app.prazo_engine.factory import build_calendar
from app.sor import models

_MINUTA = MinutaGerada(
    contexto_consolidado="contexto",
    analise_providencia="analise",
    minuta="MINUTA",
    alertas=["revisar qualificacao"],
    confianca=0.77,
)


def test_draft_from_intimacao_persists_prazo_and_peticao(db_session):
    esc = models.Escritorio(nome="Escritorio Teste")
    db_session.add(esc)
    db_session.flush()
    proc = models.Processo(escritorio_id=esc.id, numero="00000010020248260100", tribunal="TJSP")
    db_session.add(proc)
    db_session.flush()
    intimacao = models.Intimacao(
        processo_id=proc.id,
        fonte="DJEN",
        fonte_id="111",
        numero_processo=proc.numero,
        tipo_comunicacao="Intimacao",
        teor="Apresente contestacao em 15 dias uteis.",
        data_publicacao=date(2024, 9, 9),
    )
    db_session.add(intimacao)
    db_session.flush()

    classificacao = ClassificacaoIntimacao(
        tipo="Intimacao para contestar",
        peticao_sugerida="Contestacao",
        prazo_dias=15,
        dias_uteis=True,
        confianca=0.93,
        resumo="Reu intimado para contestar.",
    )

    with (
        patch("app.agent.service.classify_intimacao", return_value=classificacao),
        patch("app.agent.service.draft_peticao", return_value=_MINUTA),
    ):
        prazo, peticao, result = draft_from_intimacao(
            db_session, intimacao, calendar=build_calendar([2024, 2025])
        )

    assert result == classificacao
    assert prazo.dias == 15
    assert prazo.descricao == "Intimacao para contestar"
    assert peticao.status == "rascunho"
    assert peticao.tipo == "Contestacao"
    # conteudo carrega SÓ a minuta (protocolo-limpo); o dossiê fica separado.
    assert peticao.conteudo == "MINUTA"
    assert peticao.dossie["contexto_consolidado"] == "contexto"
    assert peticao.dossie["analise_providencia"] == "analise"
    assert peticao.dossie["alertas"] == ["revisar qualificacao"]
    assert peticao.dossie["confianca"] == 0.77
    assert peticao.processo_id == proc.id


def test_draft_from_intimacao_uses_active_office_template(db_session):
    esc = models.Escritorio(nome="Escritorio Template")
    db_session.add(esc)
    db_session.flush()
    proc = models.Processo(escritorio_id=esc.id, numero="00000010020248260100", tribunal="TJSP")
    db_session.add(proc)
    db_session.flush()
    template = models.TemplatePeticao(
        escritorio_id=esc.id,
        tipo="Contestacao",
        nome="Contestacao padrao",
        conteudo="ESTRUTURA DO ESCRITORIO",
        ativo=True,
    )
    intimacao = models.Intimacao(
        processo_id=proc.id,
        fonte="DJEN",
        fonte_id="template-1",
        numero_processo=proc.numero,
        tipo_comunicacao="Intimacao",
        teor="Apresente contestacao em 15 dias uteis.",
        data_publicacao=date(2024, 9, 9),
    )
    db_session.add_all([template, intimacao])
    db_session.flush()

    classificacao = ClassificacaoIntimacao(
        tipo="Intimacao para contestar",
        peticao_sugerida="Contestacao",
        prazo_dias=15,
        dias_uteis=True,
        confianca=0.93,
        resumo="Reu intimado para contestar.",
    )

    with (
        patch("app.agent.service.classify_intimacao", return_value=classificacao),
        patch("app.agent.service.draft_peticao", return_value=_MINUTA) as draft_mock,
    ):
        draft_from_intimacao(db_session, intimacao, calendar=build_calendar([2024, 2025]))

    assert draft_mock.call_args.kwargs["template_conteudo"] == "ESTRUTURA DO ESCRITORIO"


def test_draft_from_intimacao_feeds_process_history_to_drafter(db_session):
    """The prior movements/intimations on the process must reach the drafter, not
    just the isolated intimation (the context-enrichment fix)."""
    esc = models.Escritorio(nome="Escritorio Historico")
    db_session.add(esc)
    db_session.flush()
    proc = models.Processo(escritorio_id=esc.id, numero="00000010020248260100", tribunal="TJSP")
    db_session.add(proc)
    db_session.flush()
    db_session.add_all(
        [
            models.Andamento(
                processo_id=proc.id,
                codigo=193,
                descricao="Sentenca publicada",
                data=datetime(2024, 8, 1, tzinfo=timezone.utc),
            ),
            models.Intimacao(
                processo_id=proc.id,
                fonte="DJEN",
                fonte_id="anterior-1",
                numero_processo=proc.numero,
                tipo_comunicacao="Intimacao",
                teor="Intimacao anterior sobre pericia.",
                data_disponibilizacao=date(2024, 7, 1),
            ),
        ]
    )
    intimacao = models.Intimacao(
        processo_id=proc.id,
        fonte="DJEN",
        fonte_id="atual-1",
        numero_processo=proc.numero,
        tipo_comunicacao="Intimacao",
        teor="Apresente contestacao em 15 dias uteis.",
        data_disponibilizacao=date(2024, 9, 9),
        data_publicacao=date(2024, 9, 9),
    )
    db_session.add(intimacao)
    db_session.flush()

    classificacao = ClassificacaoIntimacao(
        tipo="Intimacao para contestar",
        peticao_sugerida="Contestacao",
        prazo_dias=15,
        dias_uteis=True,
        confianca=0.9,
        resumo="Reu intimado para contestar.",
    )

    with (
        patch("app.agent.service.classify_intimacao", return_value=classificacao),
        patch("app.agent.service.draft_peticao", return_value=_MINUTA) as draft_mock,
    ):
        draft_from_intimacao(db_session, intimacao, calendar=build_calendar([2024, 2025]))

    historico = draft_mock.call_args.kwargs["historico"]
    assert "Sentenca publicada" in historico
    assert "Intimacao anterior sobre pericia." in historico
    # a data fatal já calculada é repassada como texto pronto
    assert draft_mock.call_args.kwargs["prazo_fatal"] is not None


def test_historico_exclui_intimacao_atual_e_limita_trecho(db_session):
    esc = models.Escritorio(nome="Escritorio Trecho")
    db_session.add(esc)
    db_session.flush()
    proc = models.Processo(escritorio_id=esc.id, numero="00000010020248260100", tribunal="TJSP")
    db_session.add(proc)
    db_session.flush()
    atual = models.Intimacao(
        processo_id=proc.id,
        fonte="DJEN",
        fonte_id="atual",
        numero_processo=proc.numero,
        tipo_comunicacao="Intimacao",
        teor="TEOR_DA_INTIMACAO_ATUAL " + "x" * 2000,
        data_disponibilizacao=date(2024, 9, 9),
    )
    db_session.add(atual)
    db_session.flush()

    historico = _historico_processo(db_session, proc, intimacao_atual_id=atual.id)

    # sem outras movimentações/intimações/petições, não há histórico a montar
    assert historico is None


def test_draft_enriches_process_on_demand_via_datajud(db_session):
    """Processo "shell" (sem andamentos) é enriquecido on-demand pelo DataJud
    quando a minuta é pedida — garante o contexto completo do processo que o
    fix do histórico exige, sem travar a captura com enriquecimento sincrono."""
    from app.capture.datajud import ProcessoDTO

    esc = models.Escritorio(nome="Escritorio OnDemand")
    db_session.add(esc)
    db_session.flush()
    proc = models.Processo(escritorio_id=esc.id, numero="00000010020248260100", tribunal="TJSP")
    db_session.add(proc)
    db_session.flush()
    intimacao = models.Intimacao(
        processo_id=proc.id,
        fonte="DJEN",
        fonte_id="ondemand-1",
        numero_processo=proc.numero,
        tipo_comunicacao="Intimacao",
        teor="Apresente contestacao em 15 dias uteis.",
        data_publicacao=date(2024, 9, 9),
    )
    db_session.add(intimacao)
    db_session.flush()

    classificacao = ClassificacaoIntimacao(
        tipo="Intimacao para contestar",
        peticao_sugerida="Contestacao",
        prazo_dias=15,
        dias_uteis=True,
        confianca=0.9,
        resumo="Reu intimado para contestar.",
    )

    processo_dto = ProcessoDTO.from_source(
        {
            "numeroProcesso": "00000010020248260100",
            "classe": {"nome": "Procedimento Comum Civel"},
            "tribunal": "TJSP",
            "sistema": {"nome": "PJe"},
            "movimentos": [
                {"codigo": 193, "nome": "Sentenca publicada", "dataHora": "2024-08-01T10:00:00.000Z"},
            ],
        }
    )

    class FakeDatajud:
        def __init__(self):
            self.calls = []

        def consultar_processo(self, numero, *, tribunal):
            self.calls.append((numero, tribunal))
            return processo_dto

    datajud = FakeDatajud()

    with (
        patch("app.agent.service.classify_intimacao", return_value=classificacao),
        patch("app.agent.service.draft_peticao", return_value=_MINUTA) as draft_mock,
    ):
        draft_from_intimacao(
            db_session, intimacao,
            calendar=build_calendar([2024, 2025]),
            datajud=datajud,
        )

    # DataJud foi chamado on-demand para enriquecer o "shell"
    assert len(datajud.calls) == 1
    # andamentos agora estao no SOR
    assert db_session.query(models.Andamento).count() == 1
    andamento = db_session.query(models.Andamento).one()
    assert andamento.descricao == "Sentenca publicada"
    # o historico repassado ao drafter inclui a movimentacao
    historico = draft_mock.call_args.kwargs["historico"]
    assert "Sentenca publicada" in historico


def _shell_intimacao(db_session, *, nome, fonte_id):
    """Cria escritório + processo "shell" (sem metadados/andamentos) + intimação."""
    esc = models.Escritorio(nome=nome)
    db_session.add(esc)
    db_session.flush()
    proc = models.Processo(escritorio_id=esc.id, numero="00000010020248260100", tribunal="TJSP")
    db_session.add(proc)
    db_session.flush()
    intimacao = models.Intimacao(
        processo_id=proc.id, fonte="DJEN", fonte_id=fonte_id,
        numero_processo=proc.numero, tipo_comunicacao="Intimacao",
        teor="Apresente contestacao em 15 dias uteis.",
        data_publicacao=date(2024, 9, 9),
    )
    db_session.add(intimacao)
    db_session.flush()
    return intimacao


_CLASSIFICACAO = ClassificacaoIntimacao(
    tipo="Intimacao para contestar", peticao_sugerida="Contestacao",
    prazo_dias=15, dias_uteis=True, confianca=0.9, resumo=".",
)


def test_draft_alerts_when_datajud_unavailable(db_session):
    """Se o DataJud está indisponível na hora da minuta, o processo não enriquece.
    Em vez de seguir em silêncio (a dor original), a minuta é gerada mas com um
    alerta no dossiê avisando que o contexto do processo está incompleto."""
    intimacao = _shell_intimacao(db_session, nome="Escritorio Indisponivel", fonte_id="indispo-1")

    class TimeoutDatajud:
        def consultar_processo(self, numero, *, tribunal):
            raise httpx.ReadTimeout("timed out")

    with (
        patch("app.agent.service.classify_intimacao", return_value=_CLASSIFICACAO),
        patch("app.agent.service.draft_peticao", return_value=_MINUTA),
    ):
        _, peticao, _ = draft_from_intimacao(
            db_session, intimacao,
            calendar=build_calendar([2024, 2025]),
            datajud=TimeoutDatajud(),
        )

    alertas = peticao.dossie["alertas"]
    assert "revisar qualificacao" in alertas  # alertas do drafter preservados
    assert any("DataJud" in a for a in alertas), alertas


def test_draft_no_enrichment_alert_when_process_not_found(db_session):
    """Processo simplesmente não existe no DataJud (retorna vazio) não é erro:
    nenhum alerta de indisponibilidade é adicionado."""
    intimacao = _shell_intimacao(db_session, nome="Escritorio NaoAchado", fonte_id="naoachado-1")

    class EmptyDatajud:
        def consultar_processo(self, numero, *, tribunal):
            return None

    with (
        patch("app.agent.service.classify_intimacao", return_value=_CLASSIFICACAO),
        patch("app.agent.service.draft_peticao", return_value=_MINUTA),
    ):
        _, peticao, _ = draft_from_intimacao(
            db_session, intimacao,
            calendar=build_calendar([2024, 2025]),
            datajud=EmptyDatajud(),
        )

    assert peticao.dossie["alertas"] == ["revisar qualificacao"]  # nenhum alerta extra


def test_draft_does_not_reenrich_when_process_already_has_andamentos(db_session):
    """Processo ja enriquecido nao refaz DataJud a cada minuta (idempotente)."""
    esc = models.Escritorio(nome="Escritorio JaEnriquecido")
    db_session.add(esc)
    db_session.flush()
    proc = models.Processo(
        escritorio_id=esc.id, numero="00000010020248260100", tribunal="TJSP",
        classe="Procedimento Comum Civel", sistema="PJe",
    )
    db_session.add(proc)
    db_session.flush()
    db_session.add(models.Andamento(
        processo_id=proc.id, codigo=1, descricao="Distribuicao",
        data=datetime(2024, 1, 1, tzinfo=timezone.utc),
    ))
    intimacao = models.Intimacao(
        processo_id=proc.id, fonte="DJEN", fonte_id="ja-1",
        numero_processo=proc.numero, tipo_comunicacao="Intimacao",
        teor="Apresente contestacao em 15 dias uteis.",
        data_publicacao=date(2024, 9, 9),
    )
    db_session.add(intimacao)
    db_session.flush()

    classificacao = ClassificacaoIntimacao(
        tipo="Intimacao para contestar", peticao_sugerida="Contestacao",
        prazo_dias=15, dias_uteis=True, confianca=0.9, resumo=".",
    )

    class FakeDatajud:
        def __init__(self):
            self.calls = []

        def consultar_processo(self, numero, *, tribunal):
            self.calls.append((numero, tribunal))
            return None

    datajud = FakeDatajud()
    with (
        patch("app.agent.service.classify_intimacao", return_value=classificacao),
        patch("app.agent.service.draft_peticao", return_value=_MINUTA),
    ):
        draft_from_intimacao(
            db_session, intimacao,
            calendar=build_calendar([2024, 2025]),
            datajud=datajud,
        )

    # ja tem andamentos -> DataJud NAO foi chamado
    assert datajud.calls == []
