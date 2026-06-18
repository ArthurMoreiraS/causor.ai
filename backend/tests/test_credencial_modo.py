"""Default for credencial_assinatura.modo.

New credentials default to ``manual_handoff`` both at the ORM layer (Python
default) and at the DB layer (server_default), so the migration's added column
fills pre-existing rows without a separate backfill UPDATE.
"""

from sqlalchemy import select, text

from app.sor import models


def _seed_usuario(session) -> models.Usuario:
    escritorio = models.Escritorio(nome="Modo Test")
    session.add(escritorio)
    session.flush()
    usuario = models.Usuario(
        escritorio_id=escritorio.id, nome="Adv", email="modo@example.com"
    )
    session.add(usuario)
    session.flush()
    return usuario


def test_credencial_modo_defaults_to_manual_handoff(db_session):
    usuario = _seed_usuario(db_session)
    credencial = models.CredencialAssinatura(
        usuario_id=usuario.id,
        provedor="birdid",
        referencia_vault="localdev://x",
    )
    db_session.add(credencial)
    db_session.flush()

    assert credencial.modo == "manual_handoff"


def test_modo_server_default_fills_row_inserted_without_modo(db_session):
    """A row inserted via raw SQL that omits modo gets the server_default.

    This mirrors what ``ADD COLUMN ... DEFAULT 'manual_handoff'`` does to rows
    that existed before the migration ran.
    """
    usuario = _seed_usuario(db_session)
    db_session.execute(
        text(
            "INSERT INTO credencial_assinatura "
            "(usuario_id, provedor, referencia_vault, ativo, created_at, updated_at) "
            "VALUES (:u, 'PJeSession', 'localdev://y', 1, :ts, :ts)"
        ),
        {"u": usuario.id, "ts": "2026-06-18 00:00:00"},
    )
    db_session.flush()

    row = db_session.scalars(
        select(models.CredencialAssinatura).where(
            models.CredencialAssinatura.provedor == "PJeSession"
        )
    ).one()
    assert row.modo == "manual_handoff"


def test_modo_can_be_set_explicitly(db_session):
    usuario = _seed_usuario(db_session)
    credencial = models.CredencialAssinatura(
        usuario_id=usuario.id,
        provedor="birdid",
        referencia_vault="localdev://z",
        modo="api",
    )
    db_session.add(credencial)
    db_session.flush()

    assert credencial.modo == "api"
