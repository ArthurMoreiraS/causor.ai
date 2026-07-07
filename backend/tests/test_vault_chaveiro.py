"""TDD for the multi-court credential vault (keyring)."""

from app.sor import models
from app.vault.service import (
    find_active_session,
    load_court_session_payload,
    store_court_session,
)


def _usuario(db_session):
    esc = models.Escritorio(nome="Esc")
    db_session.add(esc)
    db_session.flush()
    u = models.Usuario(escritorio_id=esc.id, nome="Adv", email="a@e.com")
    db_session.add(u)
    db_session.flush()
    return u


def test_store_two_courts_and_find_the_right_one(db_session):
    u = _usuario(db_session)
    store_court_session(
        db_session, usuario_id=u.id, sistema="e-SAJ", tribunal="TJSP", grau="1",
        url_base="https://esaj-treino.tjsp.jus.br",
        storage_state={"cookies": [{"name": "x", "value": "s1"}]},
    )
    store_court_session(
        db_session, usuario_id=u.id, sistema="PJe", tribunal="TRT2", grau="1",
        url_base="https://pje-treino.trt2.jus.br",
        storage_state={"cookies": [{"name": "y", "value": "s2"}]},
    )

    esaj = find_active_session(
        db_session, usuario_id=u.id, sistema="e-SAJ", tribunal="TJSP", grau="1"
    )
    assert esaj is not None
    assert esaj.sistema == "e-SAJ"
    assert esaj.tipo == "session"
    assert esaj.provedor == "CourtSession"

    payload = load_court_session_payload(db_session, credencial_id=esaj.id)
    assert payload["sistema"] == "e-SAJ"
    assert payload["grau"] == "1"
    assert payload["storage_state"]["cookies"][0]["value"] == "s1"
    assert "s1" not in esaj.referencia_vault  # segredo não vaza no ref


def test_find_returns_none_when_no_session_for_court(db_session):
    u = _usuario(db_session)
    assert (
        find_active_session(
            db_session, usuario_id=u.id, sistema="PJe", tribunal="TJMG", grau="1"
        )
        is None
    )
