"""Equipe do escritório: convite, papel e desativação de membros.

A lista de membros é ``GET /usuarios`` (todos veem). Alterar a equipe é do
administrador. Nada é apagado: membro desativado perde o acesso, mas continua
como autor na auditoria e como responsável do que já tinha.
"""

from __future__ import annotations

import re
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.schemas import UsuarioOut
from app.auth.convite import Convidador, ConviteIndisponivel, get_convidador
from app.auth.jwt_auth import CurrentUser
from app.auth.papeis import Papel, requer
from app.auth.tenant import get_owned_or_404
from app.sor import models
from app.sor.db import get_session

router = APIRouter(tags=["equipe"])

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_FALHA_CONVITE = "Não foi possível enviar o convite agora. Tente de novo em instantes."


class ConviteIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    nome: str = Field(min_length=2, max_length=255)
    email: str = Field(max_length=255)
    papel: Papel
    oab: str | None = Field(default=None, max_length=20)
    oab_uf: str | None = Field(default=None, max_length=2)

    @field_validator("email")
    @classmethod
    def _email(cls, valor: str) -> str:
        valor = valor.lower()
        if not _EMAIL.match(valor):
            raise ValueError("e-mail inválido")
        return valor

    @field_validator("oab", "oab_uf")
    @classmethod
    def _vazio_e_nulo(cls, valor: str | None) -> str | None:
        return valor or None


class MembroPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    papel: Papel | None = None
    ativo: bool | None = None


class ConviteOut(BaseModel):
    membro: UsuarioOut
    convite: Literal["enviado", "ja_cadastrado", "manual"]


def _audit(session: Session, current: CurrentUser, acao: str, membro_id: int, detalhe: dict) -> None:
    session.add(models.AuditLog(
        escritorio_id=current.escritorio_id, ator=f"usuario:{current.usuario_id}",
        acao=acao, entidade="usuario", entidade_id=membro_id, detalhe=detalhe,
    ))


def _convidar(convidador: Convidador | None, membro: models.Usuario) -> str:
    if convidador is None:
        return "manual"
    try:
        return convidador.convidar(email=membro.email, nome=membro.nome)
    except ConviteIndisponivel as exc:
        raise HTTPException(status_code=502, detail=_FALHA_CONVITE) from exc


@router.post("/equipe/convites", response_model=ConviteOut, status_code=201)
def convidar_membro(
    payload: ConviteIn,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(requer("gerir_equipe")),
    convidador: Convidador | None = Depends(get_convidador),
) -> ConviteOut:
    existente = session.scalar(
        select(models.Usuario).where(func.lower(models.Usuario.email) == payload.email)
    )
    if existente is not None:
        if existente.escritorio_id == current.escritorio_id:
            raise HTTPException(409, "Esta pessoa já é membro do escritório.")
        raise HTTPException(409, "Este e-mail já está cadastrado no Causor.")
    membro = models.Usuario(
        escritorio_id=current.escritorio_id,
        nome=payload.nome,
        email=payload.email,
        papel=payload.papel,
        oab=payload.oab,
        oab_uf=payload.oab_uf.upper() if payload.oab_uf else None,
        ativo=True,
    )
    session.add(membro)
    session.flush()
    try:
        convite = _convidar(convidador, membro)
    except HTTPException:
        session.rollback()
        raise
    _audit(session, current, "membro_convidado", membro.id, {"papel": membro.papel, "convite": convite})
    session.commit()
    session.refresh(membro)
    return ConviteOut(membro=UsuarioOut.model_validate(membro), convite=convite)


@router.post("/equipe/{membro_id}/convite", response_model=ConviteOut)
def reenviar_convite(
    membro_id: int,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(requer("gerir_equipe")),
    convidador: Convidador | None = Depends(get_convidador),
) -> ConviteOut:
    membro = get_owned_or_404(session, models.Usuario, membro_id, current)
    if membro.supabase_user_id is not None:
        raise HTTPException(409, "Este membro já entrou no Causor.")
    if not membro.ativo:
        raise HTTPException(409, "Reative o membro antes de reenviar o convite.")
    convite = _convidar(convidador, membro)
    _audit(session, current, "membro_convite_reenviado", membro.id, {"convite": convite})
    session.commit()
    return ConviteOut(membro=UsuarioOut.model_validate(membro), convite=convite)


@router.patch("/equipe/{membro_id}", response_model=UsuarioOut)
def alterar_membro(
    membro_id: int,
    payload: MembroPatch,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(requer("gerir_equipe")),
) -> models.Usuario:
    # Serializa mudanças de equipe do escritório: dois administradores não
    # podem rebaixar um ao outro ao mesmo tempo e deixar o escritório sem admin.
    session.scalar(select(models.Escritorio.id).where(
        models.Escritorio.id == current.escritorio_id).with_for_update())
    membro = get_owned_or_404(session, models.Usuario, membro_id, current)
    mudancas = {
        campo: valor for campo, valor in payload.model_dump(exclude_none=True).items()
        if getattr(membro, campo) != valor
    }
    if not mudancas:
        return membro
    if membro.id == current.usuario_id:
        raise HTTPException(409, "Você não pode alterar o próprio papel nem se desativar.")
    deixa_de_ser_admin = (
        membro.papel == "administrador" and membro.ativo
        and (mudancas.get("papel", "administrador") != "administrador" or mudancas.get("ativo") is False)
    )
    if deixa_de_ser_admin:
        outros_admins = session.scalar(select(func.count()).select_from(models.Usuario).where(
            models.Usuario.escritorio_id == current.escritorio_id,
            models.Usuario.papel == "administrador",
            models.Usuario.ativo.is_(True),
            models.Usuario.id != membro.id,
        ))
        if not outros_admins:
            raise HTTPException(409, "O escritório precisa de ao menos um administrador ativo.")
    if "papel" in mudancas:
        _audit(session, current, "membro_papel_alterado", membro.id,
               {"de": membro.papel, "para": mudancas["papel"]})
        membro.papel = mudancas["papel"]
    if "ativo" in mudancas:
        _audit(session, current, "membro_reativado" if mudancas["ativo"] else "membro_desativado",
               membro.id, {})
        membro.ativo = mudancas["ativo"]
    session.commit()
    session.refresh(membro)
    return membro
