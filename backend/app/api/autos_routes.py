"""Endpoints de captura integral dos autos.

Plano do usuário (JWT): dispara captura por grau e consulta status.
Plano do agente (``Authorization: Agent``): manifesto inicial, tickets de
upload, confirmação e manifesto final. ``download_ref`` nunca sai para o
frontend; segue apenas no payload do comando do agente.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.agent_routes import get_agent_principal
from app.auth.jwt_auth import CurrentUser, get_current_user
from app.autos.contracts import ManifestInput
from app.autos import service as autos_service
from app.capture.court_routing import resolve_route
from app.settings import settings
from app.sor import models
from app.sor.db import get_session
from app.storage.objects import get_object_store

router = APIRouter(tags=["autos"])


class CapturarAutosIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    graus: list[str] = ["1", "2"]


class CapturaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    processo_instancia_id: int
    generation: int
    status: str
    expected_count: int
    captured_count: int
    missing_count: int
    error_code: str | None
    started_at: datetime | None
    completed_at: datetime | None


class InstanciaStatusOut(BaseModel):
    processo_instancia_id: int
    sistema: str
    tribunal: str
    grau: str
    captura: CapturaOut | None


class AutosStatusOut(BaseModel):
    processo_id: int
    instancias: list[InstanciaStatusOut]


class UploadTicketIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sha256: str
    size_bytes: int
    content_type: str = "application/pdf"


class UploadTicketOut(BaseModel):
    key: str
    method: str
    url: str
    headers: dict[str, str]
    expires_in: int


class ConfirmUploadIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    object_key: str
    sha256: str
    mime_type: str = "application/pdf"


class ItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    external_id: str
    status: str
    error_code: str | None


def _get_owned_processo(
    session: Session, processo_id: int, current: CurrentUser
) -> models.Processo:
    processo = session.get(models.Processo, processo_id)
    if processo is None or processo.escritorio_id != current.escritorio_id:
        raise HTTPException(status_code=404, detail="processo nao encontrado")
    return processo


def _get_agent_capture(
    session: Session, capture_id: int, installation: models.AgentInstallation
) -> models.CapturaAutos:
    capture = session.get(models.CapturaAutos, capture_id)
    if capture is None or capture.escritorio_id != installation.escritorio_id:
        raise HTTPException(status_code=404, detail="captura nao encontrada")
    return capture


@router.post("/processos/{processo_id}/autos/capturar", response_model=list[CapturaOut])
def capturar_autos(
    processo_id: int,
    payload: CapturarAutosIn | None = None,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(get_current_user),
) -> list[models.CapturaAutos]:
    processo = _get_owned_processo(session, processo_id, current)
    graus = payload.graus if payload else ["1", "2"]
    if not graus or any(grau not in {"1", "2"} for grau in graus):
        raise HTTPException(status_code=422, detail="graus deve conter apenas '1' e/ou '2'")

    captures: list[models.CapturaAutos] = []
    for grau in graus:
        route = resolve_route(processo.tribunal, grau)
        sistema = (processo.sistema or (route.sistema if route else None) or "PJe")
        tribunal = processo.tribunal or "DESCONHECIDO"
        instancia = session.scalars(
            select(models.ProcessoInstancia).where(
                models.ProcessoInstancia.processo_id == processo.id,
                models.ProcessoInstancia.sistema == sistema,
                models.ProcessoInstancia.tribunal == tribunal,
                models.ProcessoInstancia.grau == grau,
            )
        ).first()
        if instancia is None:
            instancia = models.ProcessoInstancia(
                processo_id=processo.id,
                escritorio_id=processo.escritorio_id,
                sistema=sistema,
                tribunal=tribunal,
                grau=grau,
                url_base=route.url_login if route else None,
                status="active",
            )
            session.add(instancia)
            session.flush()
        captures.append(
            autos_service.open_capture(
                session, processo_instancia=instancia, usuario_id=current.usuario_id
            )
        )
    session.commit()
    return captures


@router.get("/processos/{processo_id}/autos/status", response_model=AutosStatusOut)
def status_autos(
    processo_id: int,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(get_current_user),
) -> AutosStatusOut:
    processo = _get_owned_processo(session, processo_id, current)
    instancias = list(
        session.scalars(
            select(models.ProcessoInstancia).where(
                models.ProcessoInstancia.processo_id == processo.id
            )
        )
    )
    result: list[InstanciaStatusOut] = []
    for instancia in instancias:
        latest = session.scalars(
            select(models.CapturaAutos)
            .where(models.CapturaAutos.processo_instancia_id == instancia.id)
            .order_by(models.CapturaAutos.generation.desc())
            .limit(1)
        ).first()
        result.append(
            InstanciaStatusOut(
                processo_instancia_id=instancia.id,
                sistema=instancia.sistema,
                tribunal=instancia.tribunal,
                grau=instancia.grau,
                captura=CapturaOut.model_validate(latest) if latest else None,
            )
        )
    return AutosStatusOut(processo_id=processo.id, instancias=result)


@router.put("/agent/captures/{capture_id}/manifest/initial", response_model=CapturaOut)
def manifesto_inicial(
    capture_id: int,
    manifest: ManifestInput,
    session: Session = Depends(get_session),
    installation: models.AgentInstallation = Depends(get_agent_principal),
) -> models.CapturaAutos:
    capture = _get_agent_capture(session, capture_id, installation)
    try:
        autos_service.record_initial_manifest(session, capture=capture, manifest=manifest)
    except autos_service.CaptureError as exc:
        raise HTTPException(status_code=409, detail=exc.code) from exc
    session.commit()
    return capture


@router.post(
    "/agent/captures/{capture_id}/documents/{external_id}/upload-ticket",
    response_model=UploadTicketOut,
)
def ticket_upload_documento(
    capture_id: int,
    external_id: str,
    payload: UploadTicketIn,
    session: Session = Depends(get_session),
    installation: models.AgentInstallation = Depends(get_agent_principal),
) -> UploadTicketOut:
    capture = _get_agent_capture(session, capture_id, installation)
    item = session.scalars(
        select(models.ManifestoItem).where(
            models.ManifestoItem.captura_id == capture.id,
            models.ManifestoItem.external_id == external_id,
        )
    ).first()
    if item is None:
        raise HTTPException(status_code=404, detail="item nao encontrado")
    if payload.size_bytes > settings.agent_max_upload_bytes:
        raise HTTPException(status_code=413, detail="arquivo acima do limite")

    instancia = session.get(models.ProcessoInstancia, capture.processo_instancia_id)
    key = (
        f"tenant/{capture.escritorio_id}/process/{instancia.processo_id}"
        f"/instance/{instancia.id}/document/{item.documento_id}/{payload.sha256}.bin"
    )
    ticket = get_object_store().create_upload_ticket(
        key, payload.content_type, payload.sha256, payload.size_bytes
    )
    return UploadTicketOut(
        key=ticket.key,
        method=ticket.method,
        url=ticket.url,
        headers=ticket.headers,
        expires_in=ticket.expires_in,
    )


@router.post(
    "/agent/captures/{capture_id}/documents/{external_id}/confirm",
    response_model=ItemOut,
)
def confirmar_documento(
    capture_id: int,
    external_id: str,
    payload: ConfirmUploadIn,
    session: Session = Depends(get_session),
    installation: models.AgentInstallation = Depends(get_agent_principal),
) -> models.ManifestoItem:
    capture = _get_agent_capture(session, capture_id, installation)
    if not payload.object_key.startswith(f"tenant/{capture.escritorio_id}/"):
        raise HTTPException(status_code=403, detail="chave fora do tenant da captura")
    try:
        autos_service.confirm_document_upload(
            session,
            capture=capture,
            external_id=external_id,
            object_key=payload.object_key,
            reported_sha256=payload.sha256,
            object_store=get_object_store(),
            mime_type=payload.mime_type,
        )
    except autos_service.CaptureError as exc:
        session.commit()  # o item failed/error_code persiste para auditoria
        raise HTTPException(status_code=422, detail=exc.code) from exc
    session.commit()
    item = session.scalars(
        select(models.ManifestoItem).where(
            models.ManifestoItem.captura_id == capture.id,
            models.ManifestoItem.external_id == external_id,
        )
    ).first()
    return item


@router.put("/agent/captures/{capture_id}/manifest/final", response_model=CapturaOut)
def manifesto_final(
    capture_id: int,
    manifest: ManifestInput,
    session: Session = Depends(get_session),
    installation: models.AgentInstallation = Depends(get_agent_principal),
) -> models.CapturaAutos:
    capture = _get_agent_capture(session, capture_id, installation)
    try:
        autos_service.finalize_capture(session, capture=capture, final_manifest=manifest)
    except autos_service.CaptureError as exc:
        raise HTTPException(status_code=409, detail=exc.code) from exc
    session.commit()
    return capture
