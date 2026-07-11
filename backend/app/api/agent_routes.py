"""Endpoints do protocolo do agente local.

Dois planos de autenticação: o usuário (JWT) cria códigos de pareamento e
gerencia instalações; o agente (``Authorization: Agent <token>``) pareia,
reivindica e conclui comandos. Nenhuma resposta expõe ``token_hash`` nem
segredos de tribunal.
"""

from __future__ import annotations

from datetime import datetime
from hashlib import sha256 as sha256_digest

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent_runtime.auth import (
    AgentAuthError,
    authenticate_agent_token,
    consume_pairing_code,
    create_pairing_code,
)
from app.agent_runtime.service import (
    AgentCommandOwnershipError,
    AgentCommandTransitionError,
    complete_command,
    fail_command,
    heartbeat_command,
)
from app.auth.jwt_auth import CurrentUser, get_current_user
from app.agent_runtime import service
from app.connectors import sessions as court_sessions
from app.settings import settings
from app.sor import models
from app.sor.db import get_session
from app.storage.objects import LocalObjectStore, UnsafeObjectKeyError

router = APIRouter(tags=["agent"])


def _audit(
    session: Session,
    *,
    escritorio_id: int,
    ator: str,
    acao: str,
    entidade: str,
    entidade_id: int,
    detalhe: dict | None = None,
) -> None:
    session.add(
        models.AuditLog(
            escritorio_id=escritorio_id,
            ator=ator,
            acao=acao,
            entidade=entidade,
            entidade_id=entidade_id,
            detalhe=detalhe or {},
        )
    )


def get_agent_principal(
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_session),
) -> models.AgentInstallation:
    if not authorization or not authorization.startswith("Agent "):
        raise HTTPException(status_code=401, detail="agent authentication required")
    try:
        return authenticate_agent_token(session, authorization.removeprefix("Agent ").strip())
    except AgentAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


class PairingCodeOut(BaseModel):
    code: str
    expires_at: datetime


class InstallationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    ativo: bool
    last_seen_at: datetime | None
    version: str | None


class PairIn(BaseModel):
    code: str
    installation_name: str
    version: str


class PairOut(BaseModel):
    installation: InstallationOut
    token: str


class CommandOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tipo: str
    payload: dict
    status: str


class CompleteIn(BaseModel):
    resultado: dict


class FailIn(BaseModel):
    erro_codigo: str
    erro_detalhe: str | None = None


class UploadOut(BaseModel):
    key: str
    size_bytes: int
    sha256: str


@router.post("/agent/pairing-codes", response_model=PairingCodeOut)
def criar_codigo_pareamento(
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(get_current_user),
) -> PairingCodeOut:
    usuario = session.get(models.Usuario, current.usuario_id)
    if usuario is None or usuario.escritorio_id != current.escritorio_id:
        raise HTTPException(status_code=404, detail="usuario nao encontrado")
    secret = create_pairing_code(session, usuario=usuario)
    session.commit()
    return PairingCodeOut(code=secret.code, expires_at=secret.expires_at)


@router.get("/agent/installations", response_model=list[InstallationOut])
def listar_instalacoes(
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(get_current_user),
) -> list[models.AgentInstallation]:
    return list(
        session.scalars(
            select(models.AgentInstallation)
            .where(models.AgentInstallation.escritorio_id == current.escritorio_id)
            .order_by(models.AgentInstallation.id)
        )
    )


@router.delete("/agent/installations/{installation_id}", status_code=204)
def revogar_instalacao(
    installation_id: int,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(get_current_user),
) -> None:
    installation = session.get(models.AgentInstallation, installation_id)
    if installation is None or installation.escritorio_id != current.escritorio_id:
        raise HTTPException(status_code=404, detail="instalacao nao encontrada")
    installation.ativo = False
    _audit(
        session,
        escritorio_id=current.escritorio_id,
        ator=f"usuario:{current.usuario_id}",
        acao="agent_installation_revoked",
        entidade="agent_installation",
        entidade_id=installation.id,
    )
    session.commit()


@router.post("/agent/pair", response_model=PairOut)
def parear_agente(
    payload: PairIn,
    session: Session = Depends(get_session),
) -> PairOut:
    try:
        installation, token = consume_pairing_code(
            session,
            code=payload.code,
            installation_name=payload.installation_name,
            version=payload.version,
        )
    except AgentAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    _audit(
        session,
        escritorio_id=installation.escritorio_id,
        ator=f"agent:{installation.id}",
        acao="agent_paired",
        entidade="agent_installation",
        entidade_id=installation.id,
        detalhe={"nome": installation.nome, "version": installation.version},
    )
    session.commit()
    return PairOut(installation=InstallationOut.model_validate(installation), token=token)


@router.post("/agent/commands/claim", response_model=CommandOut | None)
def reivindicar_comando(
    session: Session = Depends(get_session),
    installation: models.AgentInstallation = Depends(get_agent_principal),
) -> models.AgentCommand | None:
    command = service.claim_next_command(session, installation=installation)
    session.commit()
    return command


def _load_owned_command(
    session: Session,
    command_id: int,
    installation: models.AgentInstallation,
) -> models.AgentCommand:
    command = session.get(models.AgentCommand, command_id)
    if command is None or command.escritorio_id != installation.escritorio_id:
        raise HTTPException(status_code=404, detail="comando nao encontrado")
    return command


@router.post("/agent/commands/{command_id}/heartbeat", response_model=CommandOut)
def heartbeat(
    command_id: int,
    session: Session = Depends(get_session),
    installation: models.AgentInstallation = Depends(get_agent_principal),
) -> models.AgentCommand:
    command = _load_owned_command(session, command_id, installation)
    try:
        heartbeat_command(session, command=command, installation=installation)
    except AgentCommandOwnershipError as exc:
        raise HTTPException(status_code=404, detail="comando nao encontrado") from exc
    except AgentCommandTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    session.commit()
    return command


@router.post("/agent/commands/{command_id}/complete", response_model=CommandOut)
def concluir_comando(
    command_id: int,
    payload: CompleteIn,
    session: Session = Depends(get_session),
    installation: models.AgentInstallation = Depends(get_agent_principal),
) -> models.AgentCommand:
    command = _load_owned_command(session, command_id, installation)
    already_completed = command.status == "completed"
    try:
        complete_command(
            session, command=command, installation=installation, resultado=payload.resultado
        )
    except AgentCommandOwnershipError as exc:
        raise HTTPException(status_code=404, detail="comando nao encontrado") from exc
    except AgentCommandTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not already_completed and command.tipo == "open_court_login":
        court_sessions.apply_login_result(
            session, command=command, installation=installation, resultado=payload.resultado
        )
    if not already_completed:
        _audit(
            session,
            escritorio_id=command.escritorio_id,
            ator=f"agent:{installation.id}",
            acao="agent_command_completed",
            entidade="agent_command",
            entidade_id=command.id,
            detalhe={"tipo": command.tipo},
        )
    session.commit()
    return command


@router.post("/agent/commands/{command_id}/fail", response_model=CommandOut)
def falhar_comando(
    command_id: int,
    payload: FailIn,
    session: Session = Depends(get_session),
    installation: models.AgentInstallation = Depends(get_agent_principal),
) -> models.AgentCommand:
    command = _load_owned_command(session, command_id, installation)
    already_failed = command.status == "failed"
    try:
        fail_command(
            session,
            command=command,
            installation=installation,
            erro_codigo=payload.erro_codigo,
            erro_detalhe=payload.erro_detalhe,
        )
    except AgentCommandOwnershipError as exc:
        raise HTTPException(status_code=404, detail="comando nao encontrado") from exc
    except AgentCommandTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not already_failed and command.tipo == "open_court_login":
        court_sessions.apply_login_failure(
            session, command=command, installation=installation, erro_codigo=payload.erro_codigo
        )
    if not already_failed:
        _audit(
            session,
            escritorio_id=command.escritorio_id,
            ator=f"agent:{installation.id}",
            acao="agent_command_failed",
            entidade="agent_command",
            entidade_id=command.id,
            detalhe={"tipo": command.tipo, "erro_codigo": payload.erro_codigo},
        )
    session.commit()
    return command


@router.put("/agent/uploads/local", response_model=UploadOut)
async def upload_local(
    request: Request,
    key: str = Query(...),
    session: Session = Depends(get_session),
    installation: models.AgentInstallation = Depends(get_agent_principal),
) -> UploadOut:
    if settings.object_store_provider != "localdev":
        raise HTTPException(status_code=404, detail="upload local indisponivel")
    required_prefix = f"tenant/{installation.escritorio_id}/"
    if not key.startswith(required_prefix):
        raise HTTPException(status_code=403, detail="chave fora do tenant do agente")

    body = await request.body()
    if len(body) > settings.agent_max_upload_bytes:
        raise HTTPException(status_code=413, detail="upload acima do limite")

    declared_size = request.headers.get("x-causor-size")
    if declared_size is not None and declared_size != str(len(body)):
        raise HTTPException(status_code=400, detail="tamanho declarado nao confere")
    declared_hash = request.headers.get("x-causor-sha256")
    digest = sha256_digest(body).hexdigest()
    if declared_hash is not None and declared_hash.lower() != digest:
        raise HTTPException(status_code=400, detail="hash declarado nao confere")

    content_type = request.headers.get("content-type", "application/octet-stream")
    store = LocalObjectStore(settings.object_store_local_path)
    try:
        stored = store.put_bytes(key, body, content_type)
    except UnsafeObjectKeyError as exc:
        raise HTTPException(status_code=400, detail="chave de objeto invalida") from exc
    return UploadOut(key=stored.key, size_bytes=stored.size_bytes, sha256=stored.sha256)
