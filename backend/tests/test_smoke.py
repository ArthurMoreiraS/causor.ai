"""Smoke tests: the package imports and the SOR schema builds."""

from sqlalchemy import inspect

from app.settings import settings
from app.sor import models


def test_settings_import():
    assert settings.djen_base_url.startswith("https://")


def test_all_tables_created(db_session):
    inspector = inspect(db_session.get_bind())
    tables = set(inspector.get_table_names())
    expected = {
        "escritorio",
        "usuario",
        "cliente",
        "processo",
        "intimacao",
        "prazo",
        "peticao",
        "andamento",
        "documento",
        "credencial_assinatura",
        "audit_log",
    }
    assert expected.issubset(tables)


def test_insert_processo_roundtrip(db_session):
    esc = models.Escritorio(nome="Escritório Teste")
    db_session.add(esc)
    db_session.flush()

    proc = models.Processo(
        escritorio_id=esc.id, numero="0000001-00.2024.8.26.0100", tribunal="TJSP"
    )
    db_session.add(proc)
    db_session.commit()

    fetched = db_session.query(models.Processo).filter_by(numero=proc.numero).one()
    assert fetched.tribunal == "TJSP"
    assert fetched.escritorio.nome == "Escritório Teste"
