"""Manual intake and persistent work, independent of court integrations."""
import re
from uuid import UUID
from hashlib import sha256
from datetime import date, datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.office_routes import audit
from app.api.schemas import ProcessoOut
from app.auth.jwt_auth import CurrentUser, get_current_user
from app.auth.papeis import responsavel_valido
from app.auth.tenant import get_owned_or_404, tenant_select
from app.capture.normalize import canonical_numero
from app.autos.context import ContextNotReadyError
from app.sor import models
from app.sor.db import get_session

router = APIRouter(tags=["trabalhos"])


class ProcessoIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    numero: str
    cliente_id: int | None = Field(None, ge=1)
    tribunal: str | None = Field(None, max_length=50)
    classe: str | None = Field(None, max_length=255)
    orgao_julgador: str | None = Field(None, max_length=255)
    sistema: Literal["PJe", "EPROC", "e-SAJ", "Projudi"] | None = None

    @field_validator("numero")
    @classmethod
    def number_format(cls, value):
        if not re.fullmatch(r"(?:[0-9]{20}|[0-9]{7}-[0-9]{2}\.[0-9]{4}\.[0-9]\.[0-9]{2}\.[0-9]{4})", value):
            raise ValueError("Informe o número CNJ com 20 dígitos, com ou sem pontuação")
        return canonical_numero(value)


class TrabalhoIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    processo_id: int = Field(ge=1)
    providencia: str = Field(min_length=3, max_length=255)
    instrucoes: str = Field("", max_length=20000)
    grau: Literal["1", "2"] = "1"
    polo: str | None = Field(None, max_length=100)
    intimacao_id: int | None = Field(None, ge=1)
    prazo_id: int | None = Field(None, ge=1)
    responsavel_id: int | None = Field(None, ge=1)


class TrabalhoPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    versao: int = Field(ge=1)
    providencia: str | None = Field(None, min_length=3, max_length=255)
    instrucoes: str | None = Field(None, max_length=20000)
    grau: Literal["1", "2"] | None = None
    polo: str | None = Field(None, max_length=100)
    responsavel_id: int | None = Field(None, ge=1)


class TrabalhoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    processo_id: int | None
    intimacao_id: int | None
    prazo_id: int | None
    peticao_id: int | None
    responsavel_id: int | None
    providencia: str
    instrucoes: str
    grau: str
    polo: str | None
    versao: int
    escopo: dict | None
    evidencias: dict | None
    created_at: datetime
    updated_at: datetime
    evidencias_atuais: bool | None = None
    motivo_revisao: str | None = None


class TrabalhosOut(BaseModel):
    total: int
    items: list[TrabalhoOut]


class VersionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    versao: int = Field(ge=1)


class EvidenceIn(VersionIn):
    perguntas: list[str] = Field(default_factory=list, max_length=20)
    fontes_fixadas: list[int] = Field(default_factory=list, max_length=40)

    @field_validator("perguntas")
    @classmethod
    def bounded_questions(cls, values):
        if any(not value.strip() or len(value) > 500 for value in values):
            raise ValueError("Cada pergunta precisa ter entre 1 e 500 caracteres")
        return [value.strip() for value in values]


class WorkOperationIn(EvidenceIn):
    acao: Literal["analise", "minuta"]
    request_id: UUID


@router.post("/trabalhos/{work_id}/operacoes", status_code=202)
def create_work_operation(work_id: int, payload: WorkOperationIn, session: Session = Depends(get_session),
                          current: CurrentUser = Depends(get_current_user)):
    from app.queue.work_jobs import enqueue_work_job, public_job

    owned = get_owned_or_404(session, models.TrabalhoJuridico, work_id, current)
    if owned.processo_id:
        session.execute(select(models.Processo.id).where(models.Processo.id == owned.processo_id).with_for_update())
    work = session.scalar(tenant_select(models.TrabalhoJuridico, current).where(
        models.TrabalhoJuridico.id == work_id).with_for_update().execution_options(populate_existing=True))
    try:
        job = enqueue_work_job(session, work=work, user_id=current.usuario_id,
            action=payload.acao, version=payload.versao, request_id=str(payload.request_id),
            questions=payload.perguntas if payload.acao == "analise" else (),
            pinned=payload.fontes_fixadas if payload.acao == "analise" else ())
    except ValueError as exc:
        session.rollback()
        raise HTTPException(409, str(exc)) from exc
    session.commit()
    return public_job(job)


def _owned_operation(session, current, work_id, job):
    from app.queue.work_jobs import public_job

    payload = job.payload or {}
    if (job.entidade != "trabalho_juridico" or job.entidade_id != work_id or
            job.tipo not in {"analise_trabalho", "minuta_trabalho"} or
            payload.get("escritorio_id") != current.escritorio_id or
            payload.get("usuario_id") != current.usuario_id):
        raise HTTPException(404, "Operação não encontrada")
    return public_job(job)


@router.get("/trabalhos/{work_id}/operacoes/atual")
def get_current_work_operation(work_id: int, session: Session = Depends(get_session),
                               current: CurrentUser = Depends(get_current_user)):
    get_owned_or_404(session, models.TrabalhoJuridico, work_id, current)
    jobs = session.scalars(select(models.JobExecucao).where(
        models.JobExecucao.entidade == "trabalho_juridico",
        models.JobExecucao.entidade_id == work_id,
        models.JobExecucao.tipo.in_(["analise_trabalho", "minuta_trabalho"]),
        models.JobExecucao.payload["escritorio_id"].as_integer() == current.escritorio_id,
        models.JobExecucao.payload["usuario_id"].as_integer() == current.usuario_id,
    ).order_by(models.JobExecucao.id.desc()).limit(1)).all()
    return _owned_operation(session, current, work_id, jobs[0]) if jobs else None


@router.get("/trabalhos/{work_id}/operacoes/{job_id}")
def get_work_operation(work_id: int, job_id: int, session: Session = Depends(get_session),
                       current: CurrentUser = Depends(get_current_user)):
    get_owned_or_404(session, models.TrabalhoJuridico, work_id, current)
    job = session.scalar(select(models.JobExecucao).where(
        models.JobExecucao.id == job_id,
        models.JobExecucao.entidade == "trabalho_juridico",
        models.JobExecucao.entidade_id == work_id,
        models.JobExecucao.payload["escritorio_id"].as_integer() == current.escritorio_id,
        models.JobExecucao.payload["usuario_id"].as_integer() == current.usuario_id))
    if job is None:
        raise HTTPException(404, "Operação não encontrada")
    return _owned_operation(session, current, work_id, job)


class PieceIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    nome: str = Field(min_length=1, max_length=255)
    pagina_inicio: int = Field(ge=1)
    pagina_fim: int = Field(ge=1)


class DocumentScopeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    versao_id: int = Field(ge=1)
    origem: Literal["autos_enviados", "subsidio_cliente", "fonte_externa"]
    pecas: list[PieceIn] = Field(default_factory=list, max_length=500)


class ScopeIn(VersionIn):
    data_referencia: date
    declaracao: str = Field(min_length=20, max_length=3000)
    documentos: list[DocumentScopeIn] = Field(default_factory=list, max_length=500)


def locked_work(session, current, work_id, version):
    owned = get_owned_or_404(session, models.TrabalhoJuridico, work_id, current)
    if owned.processo_id:
        session.execute(select(models.Processo.id).where(models.Processo.id == owned.processo_id).with_for_update())
    work = session.scalar(tenant_select(models.TrabalhoJuridico, current).where(
        models.TrabalhoJuridico.id == work_id).with_for_update().execution_options(populate_existing=True))
    if work is None:
        raise HTTPException(404, "Trabalho não encontrado")
    if work.versao != version:
        raise HTTPException(409, "O trabalho mudou. Reabra a versão atual antes de continuar.")
    return work


@router.put("/trabalhos/{work_id}/escopo", response_model=TrabalhoOut)
def declare_scope(work_id: int, payload: ScopeIn, session: Session = Depends(get_session), current: CurrentUser = Depends(get_current_user)):
    work = locked_work(session, current, work_id, payload.versao)
    if payload.data_referencia > date.today():
        raise HTTPException(422, "A data de referência não pode estar no futuro")
    if not work.processo_id:
        raise HTTPException(409, "O processo foi removido")
    if work.peticao_id:
        draft = get_owned_or_404(session, models.Peticao, work.peticao_id, current)
        if draft.status in {"aprovada", "protocolando", "protocolada"}:
            raise HTTPException(409, "Revise a aprovação antes de alterar o escopo")
    for item in payload.documentos:
        version = session.get(models.DocumentoArquivo, item.versao_id)
        document = session.get(models.Documento, version.documento_id) if version else None
        if document is None or document.escritorio_id != current.escritorio_id or document.processo_id != work.processo_id:
            raise HTTPException(404, "Documento não encontrado neste processo")
        for piece in item.pecas:
            if piece.pagina_fim < piece.pagina_inicio or not version.page_count or piece.pagina_fim > version.page_count:
                raise HTTPException(422, "Intervalo de páginas inválido ou documento ainda não processado")
    if len({item.versao_id for item in payload.documentos}) != len(payload.documentos):
        raise HTTPException(422, "Uma versão não pode aparecer duas vezes no escopo")
    work.escopo = {**payload.model_dump(mode="json", exclude={"versao"}), "origem": "declaracao_advogado",
                  "usuario_id": current.usuario_id, "declarada_em": datetime.now(timezone.utc).isoformat()}
    work.evidencias = None
    work.versao += 1
    audit(session, current, "escopo_trabalho_declarado", "trabalho_juridico", work.id, {"versao": work.versao})
    session.commit()
    return work


@router.post("/trabalhos/{work_id}/evidencias", response_model=TrabalhoOut)
def prepare_evidence(work_id: int, payload: EvidenceIn, session: Session = Depends(get_session), current: CurrentUser = Depends(get_current_user)):
    from app.agent.work_service import prepare_work_evidence
    work = locked_work(session, current, work_id, payload.versao)
    try:
        result = prepare_work_evidence(session, work=work, user_id=current.usuario_id,
                                      questions=payload.perguntas, pinned=tuple(payload.fontes_fixadas))
    except ValueError as exc:
        session.rollback()
        raise HTTPException(409, str(exc)) from exc
    except ContextNotReadyError:
        raise
    except Exception as exc:
        session.rollback()
        raise HTTPException(503, "Não foi possível concluir a análise. Suas fontes foram preservadas; tente novamente.") from exc
    audit(session, current, "evidencias_preparadas", "trabalho_juridico", work_id, {"versao": result.versao})
    session.commit()
    return result


@router.get("/trabalhos/{work_id}/fontes")
def search_work_sources(work_id: int, q: str = Query(..., min_length=1, max_length=500),
                        session: Session = Depends(get_session), current: CurrentUser = Depends(get_current_user)):
    from app.agent.evidence import original_sources
    from app.autos.context import get_ready_context
    work = get_owned_or_404(session, models.TrabalhoJuridico, work_id, current)
    process = get_owned_or_404(session, models.Processo, work.processo_id, current) if work.processo_id else None
    bundle = get_ready_context(session, processo=process) if process else None
    if bundle is None:
        raise HTTPException(409, "Processe os documentos antes de buscar fontes para o trabalho")
    return {"items": original_sources(session, processo=process, bundle=bundle, query=q, limit=30),
            "source_fingerprint": bundle.source_fingerprint}


@router.post("/trabalhos/{work_id}/evidencias/conferir", response_model=TrabalhoOut)
def review_evidence(work_id: int, payload: VersionIn, session: Session = Depends(get_session), current: CurrentUser = Depends(get_current_user)):
    from app.agent.work_service import require_current_evidence
    work = locked_work(session, current, work_id, payload.versao)
    try:
        _, evidence = require_current_evidence(session, work)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    work.evidencias = {**evidence, "conferida": True, "conferida_por": current.usuario_id,
                      "conferida_em": datetime.now(timezone.utc).isoformat()}
    work.versao += 1
    audit(session, current, "evidencias_conferidas", "trabalho_juridico", work.id, {"versao": work.versao})
    session.commit()
    return work


@router.post("/trabalhos/{work_id}/minuta", response_model=TrabalhoOut)
def generate_work_draft(work_id: int, payload: VersionIn, session: Session = Depends(get_session), current: CurrentUser = Depends(get_current_user)):
    from app.agent.work_service import draft_work
    work = locked_work(session, current, work_id, payload.versao)
    try:
        result, petition = draft_work(session, work=work, user_id=current.usuario_id)
    except ValueError as exc:
        session.rollback()
        raise HTTPException(409, str(exc)) from exc
    except Exception as exc:
        session.rollback()
        raise HTTPException(503, "Não foi possível gerar a minuta. As evidências foram preservadas; tente novamente.") from exc
    audit(session, current, "minuta_gerada", "peticao", petition.id, {"trabalho_id": work_id, "origem": "trabalho"})
    session.commit()
    return result


@router.post("/trabalhos/{work_id}/lacunas/{index}/tarefa")
def gap_task(work_id: int, index: int, payload: VersionIn,
             session: Session = Depends(get_session), current: CurrentUser = Depends(get_current_user)):
    work = locked_work(session, current, work_id, payload.versao)
    gaps = (work.evidencias or {}).get("analise", {}).get("lacunas", [])
    if not 0 <= index < len(gaps):
        raise HTTPException(404, "Lacuna não encontrada nesta análise")
    gap = gaps[index]
    key = sha256(f"work:{work.id}:{gap}".encode()).hexdigest()
    task = session.scalar(tenant_select(models.Tarefa, current).where(models.Tarefa.origem_key == key))
    if task is None:
        task = models.Tarefa(escritorio_id=current.escritorio_id, trabalho_id=work.id, processo_id=work.processo_id,
            titulo=gap[:255], descricao=gap, tipo="documento", origem="lacuna_trabalho", origem_key=key,
            origem_texto=gap, responsavel_id=work.responsavel_id)
        session.add(task)
        session.flush()
        audit(session, current, "tarefa_criada", "tarefa", task.id, {"trabalho_id": work.id, "origem": "lacuna_trabalho"})
        session.commit()
    return {"id": task.id, "trabalho_id": task.trabalho_id, "status": task.status}


@router.post("/processos", response_model=ProcessoOut, status_code=201)
def create_process(payload: ProcessoIn, response: Response, session: Session = Depends(get_session),
                   current: CurrentUser = Depends(get_current_user)):
    if payload.cliente_id is not None:
        get_owned_or_404(session, models.Cliente, payload.cliente_id, current)
    # Serialize intake within an office. The unique DB constraint also arbitrates capture races.
    session.execute(select(models.Escritorio.id).where(models.Escritorio.id == current.escritorio_id).with_for_update())
    stmt = tenant_select(models.Processo, current).where(models.Processo.numero == payload.numero)
    process = session.scalar(stmt)
    if process is None:
        process = models.Processo(escritorio_id=current.escritorio_id, **payload.model_dump())
        try:
            with session.begin_nested():
                session.add(process)
                session.flush()
        except IntegrityError:
            process = session.scalar(stmt)
            if process is None:
                raise
        else:
            audit(session, current, "processo_cadastrado_manual", "processo", process.id, {"origem": "manual"})
            session.commit()
            return process
    if payload.cliente_id is not None and process.cliente_id != payload.cliente_id:
        raise HTTPException(409, "Processo já cadastrado. Confira a parte representada na ficha antes de alterar o vínculo.")
    response.status_code = 200
    return process


@router.post("/trabalhos", response_model=TrabalhoOut, status_code=201)
def create_work(payload: TrabalhoIn, session: Session = Depends(get_session), current: CurrentUser = Depends(get_current_user)):
    get_owned_or_404(session, models.Processo, payload.processo_id, current)
    if payload.responsavel_id is not None:
        responsavel_valido(session, payload.responsavel_id, current)
    for model, field in ((models.Intimacao, "intimacao_id"), (models.Prazo, "prazo_id")):
        value = getattr(payload, field)
        if value is not None:
            entity = get_owned_or_404(session, model, value, current)
            if entity.processo_id != payload.processo_id:
                raise HTTPException(422, "A origem e o trabalho precisam pertencer ao mesmo processo")
    if payload.prazo_id and payload.intimacao_id:
        deadline = session.get(models.Prazo, payload.prazo_id)
        if deadline.intimacao_id != payload.intimacao_id:
            raise HTTPException(422, "Prazo e intimação não correspondem")
    work = models.TrabalhoJuridico(escritorio_id=current.escritorio_id, **payload.model_dump())
    session.add(work)
    session.flush()
    audit(session, current, "trabalho_criado", "trabalho_juridico", work.id, {"processo_id": work.processo_id})
    session.commit()
    return work


@router.get("/trabalhos", response_model=TrabalhosOut)
def list_works(processo_id: int | None = Query(None, ge=1), limit: int = Query(50, ge=1, le=100),
               offset: int = Query(0, ge=0), session: Session = Depends(get_session), current: CurrentUser = Depends(get_current_user)):
    stmt = tenant_select(models.TrabalhoJuridico, current)
    if processo_id is not None:
        get_owned_or_404(session, models.Processo, processo_id, current)
        stmt = stmt.where(models.TrabalhoJuridico.processo_id == processo_id)
    total = session.scalar(select(func.count()).select_from(stmt.subquery()))
    return {"total": total, "items": session.scalars(stmt.order_by(models.TrabalhoJuridico.id.desc()).limit(limit).offset(offset)).all()}


@router.get("/trabalhos/{work_id}", response_model=TrabalhoOut)
def get_work(work_id: int, session: Session = Depends(get_session), current: CurrentUser = Depends(get_current_user)):
    from app.agent.work_service import require_current_evidence
    work = get_owned_or_404(session, models.TrabalhoJuridico, work_id, current)
    result = TrabalhoOut.model_validate(work)
    if work.evidencias:
        try:
            require_current_evidence(session, work)
            result.evidencias_atuais = True
        except ValueError as exc:
            result.evidencias_atuais, result.motivo_revisao = False, str(exc)
    return result


@router.patch("/trabalhos/{work_id}", response_model=TrabalhoOut)
def update_work(work_id: int, payload: TrabalhoPatch, session: Session = Depends(get_session), current: CurrentUser = Depends(get_current_user)):
    work = locked_work(session, current, work_id, payload.versao)
    if work.peticao_id:
        draft = get_owned_or_404(session, models.Peticao, work.peticao_id, current)
        if draft.status in {"aprovada", "protocolando", "protocolada"}:
            raise HTTPException(409, "Revise a aprovação da minuta antes de alterar o trabalho.")
    changes = payload.model_dump(exclude_unset=True, exclude={"versao"})
    if any(changes.get(key, "") is None for key in ("providencia", "instrucoes", "grau")):
        raise HTTPException(422, "Providência, instruções e grau não podem ser nulos")
    changes = {k: v for k, v in changes.items() if getattr(work, k) != v}
    if changes.get("responsavel_id"):
        responsavel_valido(session, changes["responsavel_id"], current)
    if changes:
        detail = {"campos": sorted(changes)}
        if "responsavel_id" in changes:
            detail["responsavel"] = {"de": work.responsavel_id, "para": changes["responsavel_id"]}
        for key, value in changes.items():
            setattr(work, key, value)
        work.versao += 1
        if changes.keys() - {"responsavel_id"}:
            # Trocar só o responsável não muda o que foi conferido.
            work.evidencias = None
        audit(session, current, "trabalho_atualizado", "trabalho_juridico", work.id, {**detail, "versao": work.versao})
        session.commit()
    return work
