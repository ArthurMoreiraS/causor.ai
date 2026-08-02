"""Conferência do upload contra o DataJud.

Sinal externo, não prova. Divergência é motivo para perguntar ao advogado se
faltou peça — nunca para marcar a captura como falha, porque o DataJud registra
movimento processual, não a lista de peças dos autos.
"""

import pytest

from app.autos.conferencia import CHAVE_EVIDENCIA, conferir_upload_com_datajud
from app.capture.datajud import MovimentoDTO, ProcessoDTO
from app.sor import models


class DatajudFake:
    """Cliente com a mesma superfície de `DatajudClient` usada aqui."""

    def __init__(self, dto: ProcessoDTO | None):
        self._dto = dto
        self.chamadas: list[tuple[str, str]] = []

    def consultar_processo(self, numero_processo: str, *, tribunal: str):
        self.chamadas.append((numero_processo, tribunal))
        return self._dto


def _dto(nomes: list[str]) -> ProcessoDTO:
    return ProcessoDTO(
        numero_processo="10003333820184014300",
        movimentos=[MovimentoDTO(nome=nome) for nome in nomes],
    )


@pytest.fixture
def cenario(db_session):
    esc = models.Escritorio(nome="Escritório Conferência")
    db_session.add(esc)
    db_session.flush()
    processo = models.Processo(
        escritorio_id=esc.id,
        numero="10003333820184014300",
        tribunal="TRF1",
        sistema="PJe",
    )
    db_session.add(processo)
    db_session.flush()
    instancia = models.ProcessoInstancia(
        processo_id=processo.id,
        escritorio_id=esc.id,
        sistema="PJe",
        tribunal="TRF1",
        grau="1",
    )
    db_session.add(instancia)
    db_session.flush()
    capture = models.CapturaAutos(
        escritorio_id=esc.id,
        processo_instancia_id=instancia.id,
        generation=1,
        status="complete",
        fonte="upload",
        evidence={"initial": {"completude": "declarada_pelo_advogado"}},
    )
    db_session.add(capture)
    db_session.flush()
    return capture, processo


def test_divergencia_quando_o_tribunal_registra_mais_juntadas(db_session, cenario):
    capture, processo = cenario
    datajud = DatajudFake(
        _dto(["Juntada de Petição", "Juntada de Documento", "Conclusão"])
    )

    resultado = conferir_upload_com_datajud(
        db_session,
        capture=capture,
        processo=processo,
        arquivos_recebidos=1,
        datajud=datajud,
    )

    assert resultado.consultado is True
    assert resultado.movimentos == 3
    assert resultado.juntadas == 2
    assert resultado.divergencia is True
    assert datajud.chamadas == [("10003333820184014300", "TRF1")]


def test_sem_divergencia_quando_recebemos_ao_menos_as_juntadas(db_session, cenario):
    capture, processo = cenario
    datajud = DatajudFake(_dto(["Juntada de Petição", "Conclusão"]))

    resultado = conferir_upload_com_datajud(
        db_session,
        capture=capture,
        processo=processo,
        arquivos_recebidos=3,
        datajud=datajud,
    )

    assert resultado.divergencia is False


def test_conta_juntada_sem_acento_e_em_caixa_alta(db_session, cenario):
    capture, processo = cenario
    datajud = DatajudFake(_dto(["JUNTADA DE PETICAO", "juntada de documento"]))

    resultado = conferir_upload_com_datajud(
        db_session,
        capture=capture,
        processo=processo,
        arquivos_recebidos=5,
        datajud=datajud,
    )

    assert resultado.juntadas == 2


def test_processo_ausente_no_datajud_nao_vira_divergencia(db_session, cenario):
    capture, processo = cenario

    resultado = conferir_upload_com_datajud(
        db_session,
        capture=capture,
        processo=processo,
        arquivos_recebidos=1,
        datajud=DatajudFake(None),
    )

    assert resultado.consultado is False
    assert resultado.divergencia is False
    assert resultado.motivo == "processo_nao_encontrado"


def test_sem_tribunal_nao_consulta(db_session, cenario):
    capture, processo = cenario
    processo.tribunal = None
    db_session.flush()
    datajud = DatajudFake(_dto(["Juntada de Petição"]))

    resultado = conferir_upload_com_datajud(
        db_session,
        capture=capture,
        processo=processo,
        arquivos_recebidos=1,
        datajud=datajud,
    )

    assert resultado.consultado is False
    assert resultado.motivo == "sem_tribunal"
    assert datajud.chamadas == []


def test_falha_do_datajud_nao_derruba_a_captura(db_session, cenario):
    capture, processo = cenario

    class DatajudQuebrado:
        def consultar_processo(self, numero_processo: str, *, tribunal: str):
            raise RuntimeError("DataJud fora do ar")

    resultado = conferir_upload_com_datajud(
        db_session,
        capture=capture,
        processo=processo,
        arquivos_recebidos=1,
        datajud=DatajudQuebrado(),
    )

    assert resultado.consultado is False
    assert resultado.motivo == "erro_na_consulta"
    assert capture.status == "complete"


def test_resultado_fica_gravado_na_evidencia_sem_apagar_o_que_havia(
    db_session, cenario
):
    capture, processo = cenario
    datajud = DatajudFake(_dto(["Juntada de Petição"]))

    conferir_upload_com_datajud(
        db_session,
        capture=capture,
        processo=processo,
        arquivos_recebidos=1,
        datajud=datajud,
    )

    assert capture.evidence["initial"]["completude"] == "declarada_pelo_advogado"
    gravado = capture.evidence[CHAVE_EVIDENCIA]
    assert gravado["juntadas"] == 1
    assert gravado["arquivos_recebidos"] == 1
    assert gravado["divergencia"] is False
