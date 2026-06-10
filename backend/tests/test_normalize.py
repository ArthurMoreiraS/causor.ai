"""DB TDD for the capture normalization service."""

from datetime import date, datetime, timezone

import pytest

from app.capture.datajud import MovimentoDTO, ProcessoDTO
from app.capture.djen import ComunicacaoDTO
from app.capture.normalize import (
    canonical_numero,
    enrich_processo,
    normalize_intimacao,
)
from app.sor import models


@pytest.fixture
def escritorio(db_session):
    esc = models.Escritorio(nome="Escritório Teste")
    db_session.add(esc)
    db_session.flush()
    return esc


def _comunicacao(**over):
    base = {
        "id": "111",
        "numero_processo": "0000001-00.2024.8.26.0100",
        "siglaTribunal": "TJSP",
        "tipoComunicacao": "Intimação",
        "texto": "Intimada para manifestar em 15 dias.",
        "data_disponibilizacao": "2024-09-06",
    }
    base.update(over)
    return ComunicacaoDTO.from_item(base)


def _processo_dto(**over):
    base = {
        "numeroProcesso": "00000010020248260100",
        "classe": {"nome": "Procedimento Comum Cível"},
        "tribunal": "TJSP",
        "dataAjuizamento": "2024-01-15T00:00:00.000Z",
        "orgaoJulgador": {"nome": "1ª Vara Cível"},
        "sistema": {"nome": "PJe"},
        "movimentos": [
            {"codigo": 26, "nome": "Distribuição", "dataHora": "2024-01-15T10:00:00.000Z"},
        ],
    }
    base.update(over)
    return ProcessoDTO.from_source(base)


def test_canonical_numero_strips_mask():
    assert canonical_numero("0000001-00.2024.8.26.0100") == "00000010020248260100"
    assert canonical_numero("00000010020248260100") == "00000010020248260100"


def test_normalize_creates_intimacao(db_session, escritorio):
    intimacao = normalize_intimacao(db_session, _comunicacao(), escritorio_id=escritorio.id)
    db_session.flush()
    assert intimacao.id is not None
    assert intimacao.fonte == "DJEN"
    assert intimacao.fonte_id == "111"
    assert intimacao.tipo_comunicacao == "Intimação"
    assert intimacao.data_disponibilizacao == date(2024, 9, 6)
    assert intimacao.numero_processo == "00000010020248260100"


def test_normalize_dedupes_on_fonte_id(db_session, escritorio):
    first = normalize_intimacao(db_session, _comunicacao(), escritorio_id=escritorio.id)
    db_session.flush()
    second = normalize_intimacao(db_session, _comunicacao(), escritorio_id=escritorio.id)
    db_session.flush()
    assert first.id == second.id
    assert db_session.query(models.Intimacao).count() == 1


def test_normalize_links_existing_processo(db_session, escritorio):
    proc = models.Processo(
        escritorio_id=escritorio.id, numero="00000010020248260100", tribunal="TJSP"
    )
    db_session.add(proc)
    db_session.flush()

    intimacao = normalize_intimacao(db_session, _comunicacao(), escritorio_id=escritorio.id)
    db_session.flush()
    assert intimacao.processo_id == proc.id


def test_enrich_creates_processo_with_andamentos(db_session, escritorio):
    proc = enrich_processo(db_session, _processo_dto(), escritorio_id=escritorio.id)
    db_session.flush()
    assert proc.id is not None
    assert proc.numero == "00000010020248260100"
    assert proc.classe == "Procedimento Comum Cível"
    assert proc.sistema == "PJe"
    assert db_session.query(models.Andamento).count() == 1


def test_enrich_is_idempotent(db_session, escritorio):
    enrich_processo(db_session, _processo_dto(), escritorio_id=escritorio.id)
    db_session.flush()
    enrich_processo(db_session, _processo_dto(), escritorio_id=escritorio.id)
    db_session.flush()
    assert db_session.query(models.Processo).count() == 1
    assert db_session.query(models.Andamento).count() == 1  # no duplicate movement


def test_enrich_appends_new_andamento(db_session, escritorio):
    enrich_processo(db_session, _processo_dto(), escritorio_id=escritorio.id)
    db_session.flush()
    dto = _processo_dto()
    dto.movimentos.append(
        MovimentoDTO(codigo=51, nome="Conclusão", dataHora=datetime(2024, 2, 1, tzinfo=timezone.utc))
    )
    enrich_processo(db_session, dto, escritorio_id=escritorio.id)
    db_session.flush()
    assert db_session.query(models.Andamento).count() == 2
