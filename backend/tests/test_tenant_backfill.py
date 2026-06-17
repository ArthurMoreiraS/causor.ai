"""Regression for the tenant backfill migration (f5d8e3a2b1c4).

A demo-seed run with buggy code left intimacao/prazo/peticao rows with NULL
escritorio_id, making them invisible to tenant_select() after login. The
migration re-derives escritorio_id from the owning processo for any row still
NULL. These tests pin that SQL's behaviour: derivable rows get backfilled,
rows without a processo stay NULL, and the operation is idempotent.

The UPDATE statements mirror migration f5d8e3a2b1c4 verbatim; keep them in sync.
"""

from datetime import date

from sqlalchemy import select, text

from app.sor import models

_BACKFILL = [
    "UPDATE {t} SET escritorio_id = ("
    "SELECT p.escritorio_id FROM processo p WHERE p.id = {t}.processo_id"
    ") WHERE escritorio_id IS NULL AND processo_id IS NOT NULL"
]


def _run_backfill(session) -> None:
    for tabela in ("prazo", "peticao", "intimacao"):
        session.execute(text(_BACKFILL[0].format(t=tabela)))
    session.flush()


def _fixture_with_null_tenant(session) -> tuple[int, models.Processo]:
    escritorio = models.Escritorio(nome="Backfill Test", cnpj="00000000000191")
    session.add(escritorio)
    session.flush()
    processo = models.Processo(
        escritorio_id=escritorio.id, numero="0000000-00.2025.8.26.0100"
    )
    session.add(processo)
    session.flush()

    # Rows as the buggy seed produced them: owned by a processo but NULL tenant.
    session.add(
        models.Intimacao(
            processo_id=processo.id,
            escritorio_id=None,
            fonte="DJEN",
            fonte_id="backfill-1",
        )
    )
    session.add(
        models.Prazo(
            processo_id=processo.id,
            escritorio_id=None,
            data_inicio=date(2025, 1, 1),
            dias=15,
            data_fatal=date(2025, 1, 22),
        )
    )
    session.add(
        models.Peticao(processo_id=processo.id, escritorio_id=None, tipo="Contestação")
    )
    session.flush()
    return escritorio.id, processo


def test_backfill_sets_tenant_from_processo(db_session):
    escritorio_id, _ = _fixture_with_null_tenant(db_session)

    _run_backfill(db_session)

    for model in (models.Intimacao, models.Prazo, models.Peticao):
        rows = db_session.scalars(select(model)).all()
        assert rows
        assert all(r.escritorio_id == escritorio_id for r in rows), model.__tablename__


def test_backfill_leaves_orphan_intimacao_null(db_session):
    """An intimacao with no processo_id cannot be derived — must stay NULL."""
    session = db_session
    session.add(
        models.Intimacao(
            processo_id=None, escritorio_id=None, fonte="DJEN", fonte_id="orphan-1"
        )
    )
    session.flush()

    _run_backfill(session)

    orfa = session.scalars(
        select(models.Intimacao).where(models.Intimacao.fonte_id == "orphan-1")
    ).one()
    assert orfa.escritorio_id is None


def test_backfill_is_idempotent_and_preserves_existing_tenant(db_session):
    escritorio_id, processo = _fixture_with_null_tenant(db_session)
    # A correctly-stamped row from a *different* office must not be rewritten.
    outro = models.Escritorio(nome="Outro", cnpj="00000000000272")
    db_session.add(outro)
    db_session.flush()
    proc_outro = models.Processo(escritorio_id=outro.id, numero="111-00.2025.8.26.0100")
    db_session.add(proc_outro)
    db_session.flush()
    db_session.add(
        models.Prazo(
            processo_id=proc_outro.id,
            escritorio_id=outro.id,
            data_inicio=date(2025, 1, 1),
            dias=5,
            data_fatal=date(2025, 1, 8),
        )
    )
    db_session.flush()

    _run_backfill(db_session)
    _run_backfill(db_session)  # second run must be a no-op

    prazos = db_session.scalars(select(models.Prazo)).all()
    by_proc = {p.processo_id: p.escritorio_id for p in prazos}
    assert by_proc[processo.id] == escritorio_id
    assert by_proc[proc_outro.id] == outro.id
