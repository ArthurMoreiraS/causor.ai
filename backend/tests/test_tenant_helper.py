"""TDD do helper central de isolamento por tenant."""

import pytest
from fastapi import HTTPException

from app.auth.jwt_auth import CurrentUser
from app.auth.tenant import get_owned_or_404, tenant_select
from app.sor import models


def _two_tenants(db_session):
    a = models.Escritorio(nome="A")
    b = models.Escritorio(nome="B")
    db_session.add_all([a, b])
    db_session.flush()
    pa = models.Processo(escritorio_id=a.id, numero="A1")
    pb = models.Processo(escritorio_id=b.id, numero="B1")
    db_session.add_all([pa, pb])
    db_session.flush()
    return a, b, pa, pb


def test_tenant_select_filtra_por_escritorio(db_session):
    a, b, pa, pb = _two_tenants(db_session)
    cur = CurrentUser(usuario_id=1, escritorio_id=a.id, email="a@b.com")
    rows = db_session.scalars(tenant_select(models.Processo, cur)).all()
    assert [p.numero for p in rows] == ["A1"]


def test_get_owned_retorna_recurso_do_tenant(db_session):
    a, b, pa, pb = _two_tenants(db_session)
    cur = CurrentUser(usuario_id=1, escritorio_id=a.id, email="a@b.com")
    got = get_owned_or_404(db_session, models.Processo, pa.id, cur)
    assert got.id == pa.id


def test_get_owned_de_outro_tenant_404(db_session):
    a, b, pa, pb = _two_tenants(db_session)
    cur = CurrentUser(usuario_id=1, escritorio_id=a.id, email="a@b.com")
    with pytest.raises(HTTPException) as exc:
        get_owned_or_404(db_session, models.Processo, pb.id, cur)
    assert exc.value.status_code == 404
