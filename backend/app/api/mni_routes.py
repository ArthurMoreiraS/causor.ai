"""Rotas de credencial MNI: cadastro, lista mascarada, teste e revogação."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.jwt_auth import CurrentUser, get_current_user
from app.connectors.errors import ConnectorError
from app.connectors.mni import credentials as mni_credentials
from app.connectors.mni.client import MniClient
from app.connectors.mni.profiles import resolve_mni_profile
from app.sor import models
from app.sor.db import get_session

router = APIRouter(tags=["mni"])


class MniCredencialIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tribunal: str
    id_consultante: str
    senha: str


class MniCredencialOut(BaseModel):
    id: int
    tribunal: str
    id_consultante_mask: str
    ativo: bool
    last_validated_at: datetime | None


class MniTesteIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    numero_processo: str
    grau: str = "1"


class MniTesteOut(BaseModel):
    ok: bool
    error_code: str | None = None
    documentos: int | None = None


def _mask(value: str) -> str:
    return value[:3] + "***" if len(value) > 3 else "***"


def _out(credencial: models.MniCredencial) -> MniCredencialOut:
    return MniCredencialOut(
        id=credencial.id,
        tribunal=credencial.tribunal,
        id_consultante_mask=_mask(credencial.id_consultante),
        ativo=credencial.ativo,
        last_validated_at=credencial.last_validated_at,
    )


@router.post("/mni/credenciais", response_model=MniCredencialOut)
def cadastrar_mni(
    payload: MniCredencialIn,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(get_current_user),
) -> MniCredencialOut:
    credencial = mni_credentials.store_mni_credencial(
        session,
        escritorio_id=current.escritorio_id,
        usuario_id=current.usuario_id,
        tribunal=payload.tribunal,
        id_consultante=payload.id_consultante,
        senha=payload.senha,
    )
    session.commit()
    return _out(credencial)


@router.get("/mni/credenciais", response_model=list[MniCredencialOut])
def listar_mni(
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(get_current_user),
) -> list[MniCredencialOut]:
    rows = session.scalars(
        select(models.MniCredencial)
        .where(models.MniCredencial.escritorio_id == current.escritorio_id)
        .order_by(models.MniCredencial.tribunal)
    )
    return [_out(row) for row in rows]


@router.delete("/mni/credenciais/{credencial_id}", response_model=MniCredencialOut)
def revogar_mni(
    credencial_id: int,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(get_current_user),
) -> MniCredencialOut:
    try:
        credencial = mni_credentials.deactivate_mni_credencial(
            session, credencial_id=credencial_id, escritorio_id=current.escritorio_id
        )
    except mni_credentials.MniCredencialNotFound:
        raise HTTPException(status_code=404, detail="credencial nao encontrada")
    session.commit()
    return _out(credencial)


@router.post("/mni/credenciais/{credencial_id}/testar", response_model=MniTesteOut)
def testar_mni(
    credencial_id: int,
    payload: MniTesteIn,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(get_current_user),
) -> MniTesteOut:
    credencial = session.get(models.MniCredencial, credencial_id)
    if credencial is None or credencial.escritorio_id != current.escritorio_id:
        raise HTTPException(status_code=404, detail="credencial nao encontrada")
    profile = resolve_mni_profile(credencial.tribunal, payload.grau)
    if profile is None:
        raise HTTPException(status_code=422, detail="mni_profile_missing")
    client = MniClient(
        url_endpoint=profile.url_endpoint,
        id_consultante=credencial.id_consultante,
        senha=mni_credentials.load_credencial_senha(session, credencial),
    )
    try:
        result = client.consultar_processo(payload.numero_processo)
    except ConnectorError as exc:
        session.commit()
        return MniTesteOut(ok=False, error_code=exc.code)
    mni_credentials.mark_validated(session, credencial)
    session.commit()
    return MniTesteOut(ok=True, documentos=len(result.documentos))
