"""Endpoints de captura integral dos autos.

Plano do usuário (JWT): dispara captura por grau e consulta status.
Plano do agente (``Authorization: Agent``): manifesto inicial, tickets de
upload, confirmação e manifesto final. ``download_ref`` nunca sai para o
frontend; segue apenas no payload do comando do agente.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.agent_routes import get_agent_principal
from app.auth.jwt_auth import CurrentUser, get_current_user
from app.autos.conferencia import CHAVE_EVIDENCIA
from app.autos.contracts import ManifestInput
from app.autos import service as autos_service
from app.autos.upload import ArquivoEnviado, ingerir_autos_enviados
from app.capture.court_routing import resolve_route
from app.capture.datajud import DatajudClient
from app.settings import settings
from app.sor import models
from app.sor.db import get_session
from app.storage.objects import get_object_store

router = APIRouter(tags=["autos"])


def get_datajud_client() -> DatajudClient:
    """Cliente do DataJud para a conferência do upload.

    Uma tentativa só, de propósito: a conferência é sinal opcional e não pode
    segurar o request do advogado se o DataJud estiver lento ou fora do ar. É
    dependência para os testes poderem trocá-la sem tocar na rede.
    """
    return DatajudClient(max_attempts=1)


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
    fonte: str = "agente"
    # Só no upload: o confronto das juntadas do DataJud com os arquivos
    # entregues. Sinal, não prova — ver `autos/conferencia.py`.
    conferencia_datajud: dict | None = None


class InstanciaStatusOut(BaseModel):
    processo_instancia_id: int
    sistema: str
    tribunal: str
    grau: str
    captura: CapturaOut | None


class AutosStatusOut(BaseModel):
    processo_id: int
    instancias: list[InstanciaStatusOut]
    contexto: dict


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

    captures = [
        autos_service.open_capture(
            session,
            processo_instancia=_resolve_or_create_instancia(session, processo, grau),
            usuario_id=current.usuario_id,
        )
        for grau in graus
    ]
    session.commit()
    return captures


def _resolve_or_create_instancia(
    session: Session, processo: models.Processo, grau: str
) -> models.ProcessoInstancia:
    """A instância `(sistema, tribunal, grau)` do processo, criada se faltar."""
    route = resolve_route(processo.tribunal, grau)
    sistema = processo.sistema or (route.sistema if route else None) or "PJe"
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
    return instancia


@router.post("/processos/{processo_id}/autos/upload", response_model=CapturaOut)
async def upload_autos(
    processo_id: int,
    grau: str = Form("1"),
    arquivos: list[UploadFile] = File(default=[]),
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(get_current_user),
    datajud: DatajudClient = Depends(get_datajud_client),
) -> CapturaOut:
    """Recebe os autos que o próprio advogado baixou no tribunal.

    Único caminho de captura sem gate externo: não exige pareamento, credencial
    nem conector. A completude aqui é declarada pelo advogado, não provada
    contra a listagem do tribunal — ver ``autos/upload.py``.
    """
    processo = _get_owned_processo(session, processo_id, current)
    if grau not in {"1", "2"}:
        raise HTTPException(status_code=422, detail="grau deve ser '1' ou '2'")
    if not arquivos:
        raise HTTPException(status_code=422, detail="envie ao menos um arquivo")

    enviados: list[ArquivoEnviado] = []
    for arquivo in arquivos:
        conteudo = await arquivo.read()
        if len(conteudo) > settings.agent_max_upload_bytes:
            raise HTTPException(status_code=413, detail="arquivo acima do limite")
        # Só o nome-base: o nome vira identidade do documento lógico e não pode
        # carregar caminho.
        nome = (arquivo.filename or "documento.pdf").replace("\\", "/").split("/")[-1]
        enviados.append(
            ArquivoEnviado(
                nome=nome,
                conteudo=conteudo,
                mime_type=arquivo.content_type or "application/pdf",
            )
        )

    instancia = _resolve_or_create_instancia(session, processo, grau)
    try:
        capture = ingerir_autos_enviados(
            session,
            processo_instancia=instancia,
            usuario_id=current.usuario_id,
            arquivos=enviados,
            object_store=get_object_store(),
            datajud=datajud,
        )
    except autos_service.CaptureError as exc:
        session.rollback()
        raise HTTPException(status_code=422, detail=exc.code) from exc
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    conferencia = (capture.evidence or {}).get(CHAVE_EVIDENCIA)
    session.commit()
    # `evidence` não é serializado inteiro (carrega manifesto e download_ref);
    # sai só a conferência, que é o que a tela precisa mostrar.
    return CapturaOut.model_validate(capture).model_copy(
        update={"conferencia_datajud": conferencia}
    )


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
    from app.autos.context import _missing_reasons, latest_context

    context = latest_context(session, processo=processo)
    missing = _missing_reasons(session, processo)
    return AutosStatusOut(
        processo_id=processo.id, instancias=result,
        contexto={
            **(context.cobertura or {} if context else {}),
            "ready": not missing, "missing": missing,
            "id": context.id if context else None,
        },
    )


class NaoAplicavelIn(BaseModel):
    grau: str
    justificativa: str


@router.post("/processos/{processo_id}/autos/nao-aplicavel", response_model=CapturaOut)
def declarar_grau_nao_aplicavel(
    processo_id: int, payload: NaoAplicavelIn,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(get_current_user),
):
    process = _get_owned_processo(session, processo_id, current)
    if payload.grau not in {"1", "2"} or not 20 <= len(payload.justificativa.strip()) <= 1000:
        raise HTTPException(422, "Informe grau 1/2 e justificativa de 20 a 1000 caracteres")
    instance = _resolve_or_create_instancia(session, process, payload.grau)
    # Declaração humana não dispara leitura nem equivale a prova do tribunal.
    latest = session.scalars(select(models.CapturaAutos).where(
        models.CapturaAutos.processo_instancia_id == instance.id
    ).order_by(models.CapturaAutos.generation.desc())).first()
    if latest and latest.captured_count:
        raise HTTPException(409, "Há documentos neste grau; revise os autos antes de declarar ausência")
    capture = models.CapturaAutos(
        escritorio_id=current.escritorio_id, processo_instancia_id=instance.id,
        generation=(latest.generation + 1 if latest else 1),
        status="queued", fonte="upload",
    )
    session.add(capture)
    session.flush()
    autos_service.mark_not_applicable(session, capture=capture, evidence={
        "origem": "declaracao_advogado", "usuario_id": current.usuario_id,
        "justificativa": payload.justificativa.strip(),
    })
    session.add(models.AuditLog(
        escritorio_id=current.escritorio_id, ator=f"usuario:{current.usuario_id}",
        acao="grau_nao_aplicavel_declarado", entidade="captura_autos", entidade_id=capture.id,
        detalhe={"grau": payload.grau, "justificativa": payload.justificativa.strip()},
    ))
    session.commit()
    return capture


@router.post("/processos/{processo_id}/autos/reprocessar")
def reprocessar_autos(
    processo_id: int, session: Session = Depends(get_session),
    current: CurrentUser = Depends(get_current_user),
):
    process = _get_owned_processo(session, processo_id, current)
    from app.autos.context import build_process_context
    from app.queue.jobs import create_job

    session.execute(select(models.Processo.id).where(models.Processo.id == process.id).with_for_update())
    versions = session.scalars(select(models.DocumentoArquivo).join(models.Documento).where(
        models.Documento.processo_id == process.id, models.DocumentoArquivo.atual.is_(True)
    )).all()
    enqueued = 0
    for version in versions:
        summary = session.scalars(select(models.DocumentoResumo).where(
            models.DocumentoResumo.documento_arquivo_id == version.id
        )).first()
        if version.extraction_status == "complete" and summary and summary.status == "complete":
            continue
        job = session.scalars(select(models.JobExecucao).where(
            models.JobExecucao.tipo == "process_document", models.JobExecucao.entidade_id == version.id,
        ).order_by(models.JobExecucao.id.desc())).first()
        if job and job.status in {"queued", "running"}:
            continue
        if job:
            job.status, job.erro = "queued", None
        else:
            create_job(session, tipo="process_document", entidade="documento_arquivo",
                       entidade_id=version.id, payload={"documento_arquivo_id": version.id},
                       ator=f"usuario:{current.usuario_id}")
        enqueued += 1
    build_process_context(session, processo=process)
    session.commit()
    return {"reenfileirados": enqueued}


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


class DownloadTicketOut(BaseModel):
    url: str
    expires_in: int
    nome: str
    mime_type: str


def _current_version_for_documento(
    session: Session, documento: models.Documento
) -> models.DocumentoArquivo | None:
    return session.scalars(
        select(models.DocumentoArquivo)
        .where(
            models.DocumentoArquivo.documento_id == documento.id,
            models.DocumentoArquivo.atual.is_(True),
        )
        .order_by(models.DocumentoArquivo.id.desc())
        .limit(1)
    ).first()


def _get_owned_documento(
    session: Session, documento_id: int, current: CurrentUser
) -> models.Documento:
    documento = session.get(models.Documento, documento_id)
    if documento is None:
        raise HTTPException(status_code=404, detail="documento nao encontrado")
    escritorio_id = documento.escritorio_id
    if escritorio_id is None and documento.processo_id is not None:
        processo = session.get(models.Processo, documento.processo_id)
        escritorio_id = processo.escritorio_id if processo else None
    if escritorio_id != current.escritorio_id:
        # 404 (não 403): não revela existência de documento de outro tenant.
        raise HTTPException(status_code=404, detail="documento nao encontrado")
    return documento


@router.post("/documentos/{documento_id}/download-ticket", response_model=DownloadTicketOut)
def criar_ticket_download(
    documento_id: int,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(get_current_user),
) -> DownloadTicketOut:
    documento = _get_owned_documento(session, documento_id, current)
    version = _current_version_for_documento(session, documento)
    if version is None:
        raise HTTPException(status_code=404, detail="documento sem arquivo verificado")

    ticket = get_object_store().create_download_ticket(version.storage_key, expires_in=300)
    url = ticket.url
    if url.startswith("local-object://"):
        # Localdev: URL autenticada da API, nunca caminho de filesystem.
        url = f"/documentos/{documento.id}/conteudo"

    session.add(
        models.AuditLog(
            escritorio_id=current.escritorio_id,
            ator=f"usuario:{current.usuario_id}",
            acao="document_download_ticket_created",
            entidade="documento",
            entidade_id=documento.id,
            # A URL assinada nunca é persistida.
            detalhe={"documento_arquivo_id": version.id, "expires_in": ticket.expires_in},
        )
    )
    session.commit()
    return DownloadTicketOut(
        url=url,
        expires_in=ticket.expires_in,
        nome=documento.nome,
        mime_type=version.mime_type,
    )


@router.get("/documentos/{documento_id}/conteudo")
def conteudo_documento(
    documento_id: int,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(get_current_user),
):
    from fastapi.responses import Response

    documento = _get_owned_documento(session, documento_id, current)
    version = _current_version_for_documento(session, documento)
    if version is None:
        raise HTTPException(status_code=404, detail="documento sem arquivo verificado")
    try:
        data = get_object_store().get_bytes(version.storage_key)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="arquivo nao encontrado") from exc
    return Response(content=data, media_type=version.mime_type)


class OverrideIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str
    justification: str


@router.get("/documentos/{documento_id}/versoes/{versao_id}/conteudo")
def conteudo_versao_citada(
    documento_id: int, versao_id: int,
    session: Session = Depends(get_session), current: CurrentUser = Depends(get_current_user),
):
    from fastapi.responses import Response

    document = _get_owned_documento(session, documento_id, current)
    version = session.get(models.DocumentoArquivo, versao_id)
    if version is None or version.documento_id != document.id:
        raise HTTPException(404, "versão não encontrada")
    try:
        data = get_object_store().get_bytes(version.storage_key)
    except FileNotFoundError as exc:
        raise HTTPException(404, "arquivo não encontrado") from exc
    from hashlib import sha256

    if sha256(data).hexdigest() != version.sha256:
        raise HTTPException(409, "arquivo diverge da versão citada")
    return Response(content=data, media_type=version.mime_type)


class OverrideOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    action: str
    expires_at: datetime


@router.post("/processos/{processo_id}/contexto/override", response_model=OverrideOut)
def criar_override_contexto(
    processo_id: int,
    payload: OverrideIn,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(get_current_user),
) -> models.ContextOverride:
    from app.autos.context import create_context_override

    processo = _get_owned_processo(session, processo_id, current)
    if payload.action not in {"draft", "file"}:
        raise HTTPException(status_code=422, detail="action deve ser draft ou file")
    try:
        override = create_context_override(
            session,
            processo=processo,
            usuario_id=current.usuario_id,
            action=payload.action,
            justification=payload.justification,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    session.commit()
    return override


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
