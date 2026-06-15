"""Isolamento multi-tenant em nível de aplicação.

Todo acesso a dados passa por aqui para filtrar pelo escritorio_id do usuário
autenticado. Recursos de outro tenant retornam 404 (não revelam existência).
"""

from __future__ import annotations

from typing import TypeVar

from fastapi import HTTPException
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.auth.jwt_auth import CurrentUser

T = TypeVar("T")


def tenant_select(model: type[T], current: CurrentUser) -> Select:
    """SELECT já filtrado pelo escritorio_id do usuário. `model` precisa ter
    a coluna `escritorio_id`."""
    return select(model).where(model.escritorio_id == current.escritorio_id)


def get_owned_or_404(session: Session, model: type[T], obj_id: int, current: CurrentUser) -> T:
    """Busca por id exigindo que o recurso pertença ao tenant. 404 caso contrário."""
    obj = session.get(model, obj_id)
    if obj is None or getattr(obj, "escritorio_id", None) != current.escritorio_id:
        raise HTTPException(status_code=404, detail="não encontrado")
    return obj
