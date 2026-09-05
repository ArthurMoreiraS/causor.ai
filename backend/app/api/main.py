"""FastAPI application — read-only views over the SOR.

These endpoints are intentionally read-only. Any irreversible action
(drafting/filing) goes through the agent + human-approval gate, never a plain
REST write here.
"""

from __future__ import annotations

import base64
import binascii
import logging
from datetime import date, datetime, timedelta, timezone

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.agent.assistant import chat_with_assistant
from app.agent.service import MissingIntimationTextError, draft_from_intimacao
from app.agent.context_selection import DraftContextBudgetError
from app.alertas.radar import prazos_em_alerta
from app.auth.jwt_auth import CurrentUser, get_current_user
from app.auth.tenant import get_owned_or_404, tenant_select
from app.api.schemas import (
    AlertaPrazo,
    AuditLogOut,
    CaptureOabRequest,
    CaptureResultOut,
    ChatRequest,
    ChatResponse,
    ConfirmarProtocoloRequest,
    ConfirmarPrazoRequest,
    CourtRoutingOut,
    CreateCredencialAssinaturaRequest,
    CredencialAssinaturaOut,
    DraftRequest,
    DraftResponse,
    EditPeticaoRequest,
    IntimacaoOut,
    JobOut,
    MeOut,
    OabMonitoradaCreate,
    OabMonitoradaOut,
    OabRemovalResultOut,
    OperationalProfileOut,
    OperationalProfileUpdate,
    OperationalDashboard,
    PeticaoOut,
    PrazoOut,
    ProcessoOut,
    ProcessoResumoLista,
    ProcessoResumoOut,
    ProximoPrazoOut,
    ProtocolarAsyncRequest,
    RevisarPrazoRequest,
    ReviewQueueItem,
    TemplatePeticaoCreate,
    TemplatePeticaoOut,
    TemplatePeticaoUpdate,
    UsuarioOut,
)
from app.capture.datajud import DatajudClient, ProcessoDTO
from app.capture.djen import DjenClient
from app.capture.enrich import backfill_sistema, run_enrichment_backfill
from app.capture.poll import poll_oab
from app.filing.timbrado import LogoInvalidoError, normalize_logo
from app.prazo_engine.factory import build_calendar
from app.queue.jobs import (
    AlreadyFiledError,
    ApprovalRequiredError,
    CredencialInativaError,
    CredencialNaoEncontradaError,
    JobNotFoundError,
    PeticaoNotFoundError,
    ProcessoSemOrgaoError,
    UnsupportedFilingSystemError,
    create_job,
    get_job,
    confirm_manual_protocol,
    run_pje_protocol_job,
)
from app.settings import settings
from app.sor import models
from app.sor.db import get_session
from app.vault.service import (
    CredencialNotFoundError,
    UsuarioNotFoundError,
    deactivate_signature_credential,
    list_signature_credentials,
    store_signature_reference,
)
from app.autos.context import ContextNotReadyError
from app.capture.court_routing import resolve_route


def _default_calendar_years() -> list[int]:
    year = datetime.now(timezone.utc).year
    return [year - 1, year, year + 1]


def _audit(
    session: Session,
    *,
    acao: str,
    entidade: str,
    entidade_id: int,
    ator_id: int | None = None,
    escritorio_id: int | None = None,
    detalhe: dict | None = None,
) -> None:
    session.add(
        models.AuditLog(
            escritorio_id=escritorio_id,
            ator=f"usuario:{ator_id}" if ator_id is not None else "system",
            acao=acao,
            entidade=entidade,
            entidade_id=entidade_id,
            detalhe=detalhe or {},
        )
    )


def _require_current_escritorio_path(
    session: Session,
    escritorio_id: int,
    current: CurrentUser,
) -> None:
    if escritorio_id != current.escritorio_id or session.get(models.Escritorio, escritorio_id) is None:
        raise HTTPException(status_code=404, detail="escritorio nao encontrado")


class _NoopDatajudClient:
    def consultar_processo(self, numero_processo: str, *, tribunal: str) -> ProcessoDTO | None:
        return None


def _dias_para_vencer(prazo: models.Prazo | None) -> int | None:
    if prazo is None:
        return None
    today = datetime.now(timezone.utc).date()
    return (prazo.data_fatal - today).days


def _risco_prazo(prazo: models.Prazo | None) -> str:
    dias = _dias_para_vencer(prazo)
    if prazo is None or dias is None:
        return "sem_prazo"
    if prazo.cumprido:
        return "cumprido"
    if dias < 0:
        return "vencido"
    if dias <= 3:
        return "alto"
    if dias <= 7:
        return "medio"
    return "baixo"


def _status_revisao(
    prazo: models.Prazo | None,
    peticao: models.Peticao | None,
) -> str:
    if prazo is not None and prazo.cumprido:
        return "cumprido"
    if peticao is not None and peticao.status == "protocolada":
        return "protocolada"
    if peticao is not None and peticao.status == "aprovada":
        return "pronta_para_protocolo"
    if peticao is not None and peticao.status == "rascunho":
        return "minuta_em_revisao"
    if prazo is not None:
        return "prazo_calculado"
    return "capturada"


def _payload_matches_oab(payload: dict | None, *, oab: str, uf: str) -> bool:
    if not isinstance(payload, dict):
        return False
    oab_digits = "".join(ch for ch in oab if ch.isdigit())
    uf_upper = uf.upper()
    for item in payload.get("destinatarioadvogados") or []:
        if not isinstance(item, dict):
            continue
        advogado = item.get("advogado")
        if not isinstance(advogado, dict):
            continue
        numero = "".join(ch for ch in str(advogado.get("numero_oab") or "") if ch.isdigit())
        item_uf = str(advogado.get("uf_oab") or "").upper()
        if numero == oab_digits and item_uf == uf_upper:
            return True
    return False


def _job_matches_oab(job: models.JobExecucao, *, oab: str, uf: str) -> bool:
    payload = job.payload if isinstance(job.payload, dict) else {}
    return (
        "".join(ch for ch in str(payload.get("oab") or "") if ch.isdigit())
        == "".join(ch for ch in oab if ch.isdigit())
        and str(payload.get("uf") or "").upper() == uf.upper()
    )


def _purge_oab_data(
    session: Session,
    *,
    escritorio_id: int,
    oab: str,
    uf: str,
) -> dict[str, int]:
    counts = {
        "intimacoes": 0,
        "prazos": 0,
        "peticoes": 0,
        "processos": 0,
        "documentos": 0,
        "andamentos": 0,
        "jobs": 0,
        "auditoria": 0,
    }
    intimacoes = list(
        session.scalars(
            select(models.Intimacao).where(models.Intimacao.escritorio_id == escritorio_id)
        )
    )
    target_intimacao_ids = {
        intimacao.id
        for intimacao in intimacoes
        if _payload_matches_oab(intimacao.payload, oab=oab, uf=uf)
    }
    process_ids = {
        intimacao.processo_id for intimacao in intimacoes
        if intimacao.id in target_intimacao_ids and intimacao.processo_id is not None
    }
    target_prazo_ids = {
        prazo.id
        for prazo in session.scalars(
            select(models.Prazo).where(
                models.Prazo.escritorio_id == escritorio_id,
                models.Prazo.intimacao_id.in_(target_intimacao_ids),
            )
        )
    }
    target_peticao_ids = {
        peticao.id
        for peticao in session.scalars(
            select(models.Peticao).where(
                models.Peticao.escritorio_id == escritorio_id,
                models.Peticao.prazo_id.in_(target_prazo_ids),
            )
        )
    }

    target_process_ids: set[int] = set()
    for process_id in process_ids:
        process_intimacao_ids = {
            row.id for row in session.scalars(
                select(models.Intimacao).where(
                    models.Intimacao.escritorio_id == escritorio_id,
                    models.Intimacao.processo_id == process_id,
                )
            )
        }
        if process_intimacao_ids and process_intimacao_ids <= target_intimacao_ids:
            target_process_ids.add(process_id)

    if target_process_ids:
        target_prazo_ids.update(
            prazo.id
            for prazo in session.scalars(
                select(models.Prazo).where(
                    models.Prazo.escritorio_id == escritorio_id,
                    models.Prazo.processo_id.in_(target_process_ids),
                )
            )
        )
        target_peticao_ids.update(
            peticao.id
            for peticao in session.scalars(
                select(models.Peticao).where(
                    models.Peticao.escritorio_id == escritorio_id,
                    models.Peticao.processo_id.in_(target_process_ids),
                )
            )
        )

    from app.capture.cleanup import purge_case_dependencies

    counts["documentos"], document_entities = purge_case_dependencies(
        session, process_ids=target_process_ids, petition_ids=target_peticao_ids,
        deadline_ids=target_prazo_ids,
    )
    if target_process_ids:
        counts["andamentos"] = session.execute(
            delete(models.Andamento).where(models.Andamento.processo_id.in_(target_process_ids))
        ).rowcount or 0

    entity_ids = {
        **document_entities,
        "intimacao": target_intimacao_ids,
        "prazo": target_prazo_ids,
        "peticao": target_peticao_ids,
        "processo": target_process_ids,
    }
    # Audit records survive operational cleanup, including references to rows
    # removed below. The endpoint records a new cleanup event instead.

    job_ids = [
        job.id
        for job in session.scalars(select(models.JobExecucao))
        if isinstance(job.payload, dict)
        and str(job.payload.get("escritorio_id")) == str(escritorio_id)
        and (_job_matches_oab(job, oab=oab, uf=uf)
             or (job.entidade in entity_ids and job.entidade_id in entity_ids[job.entidade]))
    ]
    if job_ids:
        counts["jobs"] = session.execute(
            delete(models.JobExecucao).where(models.JobExecucao.id.in_(job_ids))
        ).rowcount or 0

    if target_peticao_ids:
        counts["peticoes"] = session.execute(
            delete(models.Peticao).where(models.Peticao.id.in_(target_peticao_ids))
        ).rowcount or 0
    if target_prazo_ids:
        counts["prazos"] = session.execute(
            delete(models.Prazo).where(models.Prazo.id.in_(target_prazo_ids))
        ).rowcount or 0
    counts["intimacoes"] = session.execute(
        delete(models.Intimacao).where(models.Intimacao.id.in_(target_intimacao_ids))
    ).rowcount or 0
    if target_process_ids:
        counts["processos"] = session.execute(
            delete(models.Processo).where(models.Processo.id.in_(target_process_ids))
        ).rowcount or 0
    return counts


logger = logging.getLogger(__name__)


class InternalErrorToJsonMiddleware(BaseHTTPMiddleware):
    """Converte exceção não tratada em JSON 500 dentro da cadeia de CORS.

    O `ServerErrorMiddleware` do Starlette é o mais externo de todos — por fora
    até do CORS. Deixar a exceção chegar lá produz uma resposta sem
    `Access-Control-Allow-Origin`, que o browser recusa a ler e reporta como
    `Failed to fetch`; o frontend então diz ao advogado para verificar a
    internet enquanto o problema é do servidor. Capturando aqui, a resposta
    ainda sobe pelo CORS e chega como um 500 legítimo.
    """

    async def dispatch(self, request, call_next):
        try:
            return await call_next(request)
        except Exception:
            logger.exception("erro interno em %s %s", request.method, request.url.path)
            # Detalhe da exceção pode conter caminho, SQL ou segredo: fica no log.
            return JSONResponse(
                status_code=500,
                content={"detail": {"code": "internal_error"}},
            )


def create_app() -> FastAPI:
    app = FastAPI(title="Causor API", version="0.1.0")
    # Ordem importa: `add_middleware` insere no início, então o último a ser
    # adicionado é o mais externo. O CORS precisa envolver o conversor para
    # conseguir carimbar o cabeçalho na resposta de erro.
    app.add_middleware(InternalErrorToJsonMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from app.api.agent_routes import router as agent_router
    from app.api.autos_routes import router as autos_router
    from app.api.connector_routes import router as connector_router
    from app.api.mni_routes import router as mni_router
    from app.api.office_routes import router as office_router

    app.include_router(agent_router)
    app.include_router(autos_router)
    app.include_router(connector_router)
    app.include_router(mni_router)
    app.include_router(office_router)

    @app.exception_handler(ContextNotReadyError)
    def _context_not_ready(_request, exc: ContextNotReadyError):
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=409,
            content={
                "detail": {
                    "code": exc.code,
                    "processo_id": exc.processo_id,
                    "missing": exc.missing,
                    "next_step": exc.next_step,
                    "rota": exc.rota,
                }
            },
        )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/me", response_model=MeOut)
    def me(current: CurrentUser = Depends(get_current_user)) -> MeOut:
        return MeOut(
            usuario_id=current.usuario_id,
            escritorio_id=current.escritorio_id,
            email=current.email,
        )

    @app.get("/settings/profile", response_model=OperationalProfileOut)
    def carregar_perfil_operacional(
        session: Session = Depends(get_session),
        current: CurrentUser = Depends(get_current_user),
    ) -> OperationalProfileOut:
        usuario = session.get(models.Usuario, current.usuario_id)
        escritorio = session.get(models.Escritorio, current.escritorio_id)
        if usuario is None or escritorio is None:
            raise HTTPException(status_code=404, detail="perfil nao encontrado")
        return OperationalProfileOut(usuario=usuario, escritorio=escritorio)

    @app.patch("/settings/profile", response_model=OperationalProfileOut)
    def atualizar_perfil_operacional(
        payload: OperationalProfileUpdate,
        session: Session = Depends(get_session),
        current: CurrentUser = Depends(get_current_user),
    ) -> OperationalProfileOut:
        usuario = session.get(models.Usuario, current.usuario_id)
        escritorio = session.get(models.Escritorio, current.escritorio_id)
        if usuario is None or escritorio is None or usuario.escritorio_id != escritorio.id:
            raise HTTPException(status_code=404, detail="perfil nao encontrado")

        changes: dict[str, str | None] = {}
        if payload.nome_usuario is not None:
            usuario.nome = payload.nome_usuario.strip()
            changes["nome_usuario"] = usuario.nome
        if payload.nome_escritorio is not None:
            escritorio.nome = payload.nome_escritorio.strip()
            changes["nome_escritorio"] = escritorio.nome
        if payload.cnpj is not None:
            escritorio.cnpj = payload.cnpj.strip() or None
            changes["cnpj"] = escritorio.cnpj
        if payload.oab is not None:
            usuario.oab = payload.oab.strip() or None
            changes["oab"] = usuario.oab
        if payload.oab_uf is not None:
            usuario.oab_uf = payload.oab_uf.strip().upper() or None
            changes["oab_uf"] = usuario.oab_uf
        if payload.timbrado_cabecalho is not None:
            escritorio.timbrado_cabecalho = payload.timbrado_cabecalho.strip() or None
            changes["timbrado_cabecalho"] = escritorio.timbrado_cabecalho
        if payload.timbrado_rodape is not None:
            escritorio.timbrado_rodape = payload.timbrado_rodape.strip() or None
            changes["timbrado_rodape"] = escritorio.timbrado_rodape
        if payload.timbrado_logo is not None:
            if payload.timbrado_logo == "":
                escritorio.timbrado_logo = None
                escritorio.timbrado_logo_mime = None
                changes["timbrado_logo"] = "removido"
            else:
                try:
                    bruto = base64.b64decode(payload.timbrado_logo, validate=True)
                except binascii.Error as exc:
                    raise HTTPException(
                        status_code=422, detail="logo deve ser base64 válido"
                    ) from exc
                try:
                    escritorio.timbrado_logo = normalize_logo(bruto)
                except LogoInvalidoError as exc:
                    raise HTTPException(status_code=422, detail=str(exc)) from exc
                escritorio.timbrado_logo_mime = "image/png"
                # Bytes ficam fora do audit log; registra só a ação.
                changes["timbrado_logo"] = "atualizado"

        if changes:
            _audit(
                session,
                acao="perfil_operacional_atualizado",
                entidade="usuario",
                entidade_id=usuario.id,
                ator_id=current.usuario_id,
                escritorio_id=current.escritorio_id,
                detalhe=changes,
            )
        session.commit()
        session.refresh(usuario)
        session.refresh(escritorio)
        return OperationalProfileOut(usuario=usuario, escritorio=escritorio)

    @app.get("/dashboard/operational", response_model=OperationalDashboard)
    def dashboard_operacional(
        session: Session = Depends(get_session),
        current: CurrentUser = Depends(get_current_user),
    ) -> OperationalDashboard:
        processos = len(session.scalars(tenant_select(models.Processo, current)).all())
        intimacoes = len(session.scalars(tenant_select(models.Intimacao, current)).all())
        prazos = list(session.scalars(tenant_select(models.Prazo, current)).all())
        peticoes = list(session.scalars(tenant_select(models.Peticao, current)).all())
        pending_deadlines = [prazo for prazo in prazos if not prazo.cumprido]
        today = datetime.now(timezone.utc).date()
        high_risk = [
            prazo for prazo in pending_deadlines if (prazo.data_fatal - today).days <= 3
        ]
        overdue = [prazo for prazo in pending_deadlines if prazo.data_fatal < today]

        return OperationalDashboard(
            metrics=[
                {"key": "processos", "label": "Processos monitorados", "value": processos},
                {"key": "intimacoes", "label": "Intimações capturadas", "value": intimacoes},
                {"key": "prazos", "label": "Prazos pendentes", "value": len(pending_deadlines)},
                {"key": "risco", "label": "Alto risco", "value": len(high_risk)},
                {"key": "vencidos", "label": "Prazos vencidos", "value": len(overdue)},
                {
                    "key": "minutas",
                    "label": "Minutas em revisao",
                    "value": len([p for p in peticoes if p.status == "rascunho"]),
                },
                {
                    "key": "aprovadas",
                    "label": "Minutas aprovadas",
                    "value": len([p for p in peticoes if p.status == "aprovada"]),
                },
            ],
            workflow=[
                {
                    "key": "capture",
                    "label": "Captura",
                    "detail": "DJEN + DataJud",
                    "status": "live",
                },
                {
                    "key": "deadline",
                    "label": "Prazo",
                    "detail": "Motor determinístico",
                    "status": "live",
                },
                {
                    "key": "draft",
                    "label": "Minuta",
                    "detail": "Claude + templates",
                    "status": "review",
                },
                {
                    "key": "approval",
                    "label": "Aprovação",
                    "detail": "Gate humano OAB",
                    "status": "review",
                },
                {
                    "key": "filing",
                    "label": "Protocolo",
                    "detail": "Conector PJe/e-SAJ",
                    "status": "planned",
                },
            ],
            connectors=[
                {
                    "key": "djen",
                    "name": "DJEN",
                    "detail": "captura oficial de comunicações",
                    "status": "online",
                },
                {
                    "key": "datajud",
                    "name": "DataJud",
                    "detail": "metadados e andamentos processuais",
                    "status": "online",
                },
                {
                    "key": "pje",
                    "name": "PJe",
                    "detail": "protocolo assistido por Playwright",
                    "status": "pilot",
                },
                {
                    "key": "esaj",
                    "name": "e-SAJ",
                    "detail": "próximo conector de tribunal",
                    "status": "planned",
                },
            ],
            audit_signals=[
                {
                    "key": "gate",
                    "title": "Gate humano ativo",
                    "detail": "Nenhuma petição é protocolada sem aprovação.",
                },
                {
                    "key": "secrets",
                    "title": "Segredos fora do prompt",
                    "detail": "Certificados e senhas pertencem ao vault.",
                },
                {
                    "key": "audit",
                    "title": "Trilha imutável",
                    "detail": "Cada ação do agente deve virar evento auditável.",
                },
            ],
        )

    @app.get("/audit", response_model=list[AuditLogOut])
    def listar_auditoria(
        session: Session = Depends(get_session),
        current: CurrentUser = Depends(get_current_user),
        entidade: str | None = Query(default=None),
        entidade_id: int | None = Query(default=None),
        limit: int = Query(default=100, le=500),
    ) -> list[models.AuditLog]:
        stmt = tenant_select(models.AuditLog, current)
        if entidade is not None:
            stmt = stmt.where(models.AuditLog.entidade == entidade)
        if entidade_id is not None:
            stmt = stmt.where(models.AuditLog.entidade_id == entidade_id)
        stmt = stmt.order_by(models.AuditLog.id.desc()).limit(limit)
        return list(session.scalars(stmt))

    @app.post("/jobs/capture/oab", response_model=JobOut)
    def criar_job_captura_oab(
        payload: CaptureOabRequest,
        session: Session = Depends(get_session),
        current: CurrentUser = Depends(get_current_user),
    ) -> models.JobExecucao:
        # Sem janela no payload, quem executar o job varre o histórico inteiro da
        # OAB no DJEN. O default limitado é gravado aqui, no momento da criação,
        # para que o executor não dependa de o chamador lembrar de repassá-lo.
        dados = payload.model_dump(mode="json")
        if dados.get("data_inicio") is None:
            data_fim = payload.data_fim or date.today()
            dados["data_inicio"] = (
                data_fim - timedelta(days=settings.capture_manual_lookback_days)
            ).isoformat()
            dados["data_fim"] = data_fim.isoformat()

        job = create_job(
            session,
            tipo="captura_oab",
            entidade="escritorio",
            entidade_id=current.escritorio_id,
            payload={**dados, "escritorio_id": current.escritorio_id},
            ator=f"usuario:{current.usuario_id}",
        )
        session.commit()
        session.refresh(job)
        return job

    def _job_pertence_ao_tenant(session: Session, job: models.JobExecucao, current: CurrentUser) -> bool:
        # JobExecucao não tem escritorio_id próprio; o vínculo de tenant é
        # derivado da entidade que o job referencia.
        if job.entidade == "escritorio":
            return job.entidade_id == current.escritorio_id
        if job.entidade == "oab_monitorada" and job.entidade_id is not None:
            oab = session.get(models.OabMonitorada, job.entidade_id)
            return oab is not None and oab.escritorio_id == current.escritorio_id
        if job.entidade == "peticao" and job.entidade_id is not None:
            peticao = session.get(models.Peticao, job.entidade_id)
            return peticao is not None and peticao.escritorio_id == current.escritorio_id
        # Jobs sem vínculo de tenant identificável não vazam para ninguém.
        return False

    @app.get("/jobs", response_model=list[JobOut])
    def listar_jobs(
        tipo: str | None = Query(default=None),
        status: str | None = Query(default=None),
        limit: int = Query(default=50, ge=1, le=200),
        session: Session = Depends(get_session),
        current: CurrentUser = Depends(get_current_user),
    ) -> list[models.JobExecucao]:
        stmt = select(models.JobExecucao)
        if tipo is not None:
            stmt = stmt.where(models.JobExecucao.tipo == tipo)
        if status is not None:
            stmt = stmt.where(models.JobExecucao.status == status)
        stmt = stmt.order_by(models.JobExecucao.id.desc())
        jobs = [
            job
            for job in session.scalars(stmt)
            if _job_pertence_ao_tenant(session, job, current)
        ]
        return jobs[:limit]

    @app.get("/jobs/{job_id}", response_model=JobOut)
    def consultar_job(
        job_id: int,
        session: Session = Depends(get_session),
        current: CurrentUser = Depends(get_current_user),
    ) -> models.JobExecucao:
        try:
            job = get_job(session, job_id)
        except JobNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        if not _job_pertence_ao_tenant(session, job, current):
            raise HTTPException(status_code=404, detail="job nao encontrado")
        return job

    @app.get("/capturas/oab", response_model=list[OabMonitoradaOut])
    def listar_oabs_monitoradas(
        session: Session = Depends(get_session),
        current: CurrentUser = Depends(get_current_user),
    ) -> list[models.OabMonitorada]:
        stmt = tenant_select(models.OabMonitorada, current).order_by(
            models.OabMonitorada.id.desc()
        )
        return list(session.scalars(stmt))

    @app.post("/capturas/oab", response_model=OabMonitoradaOut, status_code=201)
    def registrar_oab_monitorada(
        payload: OabMonitoradaCreate,
        session: Session = Depends(get_session),
        current: CurrentUser = Depends(get_current_user),
    ) -> models.OabMonitorada:
        existing = session.scalar(
            select(models.OabMonitorada).where(
                models.OabMonitorada.escritorio_id == current.escritorio_id,
                models.OabMonitorada.oab == payload.oab,
                models.OabMonitorada.uf == payload.uf,
            )
        )
        if existing is not None:
            existing.ativo = True
            existing.intervalo_horas = payload.intervalo_horas
            session.commit()
            session.refresh(existing)
            return existing
        oab = models.OabMonitorada(
            escritorio_id=current.escritorio_id,
            oab=payload.oab,
            uf=payload.uf,
            intervalo_horas=payload.intervalo_horas,
            ativo=True,
        )
        session.add(oab)
        session.commit()
        session.refresh(oab)
        return oab

    @app.delete("/capturas/oab/{oab_id}", response_model=OabRemovalResultOut)
    def remover_oab_monitorada(
        oab_id: int,
        purge: bool = Query(default=True),
        session: Session = Depends(get_session),
        current: CurrentUser = Depends(get_current_user),
    ) -> OabRemovalResultOut:
        oab = get_owned_or_404(session, models.OabMonitorada, oab_id, current)
        oab_numero = oab.oab
        uf = oab.uf
        counts = (
            _purge_oab_data(
                session,
                escritorio_id=current.escritorio_id,
                oab=oab_numero,
                uf=uf,
            )
            if purge
            else {}
        )
        _audit(session, acao="oab_removida", entidade="oab_monitorada", entidade_id=oab.id,
               ator_id=current.usuario_id, escritorio_id=current.escritorio_id,
               detalhe={"purge": purge, "counts": counts, "auditoria_preservada": True})
        session.delete(oab)
        session.commit()
        return OabRemovalResultOut(
            oab_id=oab_id,
            oab=oab_numero,
            uf=uf,
            purge=purge,
            removidos=counts,
        )

    @app.get("/usuarios", response_model=list[UsuarioOut])
    def listar_usuarios(
        session: Session = Depends(get_session),
        current: CurrentUser = Depends(get_current_user),
    ) -> list[models.Usuario]:
        stmt = tenant_select(models.Usuario, current).order_by(models.Usuario.id)
        return list(session.scalars(stmt))

    @app.post(
        "/usuarios/{usuario_id}/credenciais-assinatura",
        response_model=CredencialAssinaturaOut,
    )
    def cadastrar_credencial_assinatura(
        usuario_id: int,
        payload: CreateCredencialAssinaturaRequest,
        session: Session = Depends(get_session),
        current: CurrentUser = Depends(get_current_user),
    ) -> models.CredencialAssinatura:
        get_owned_or_404(session, models.Usuario, usuario_id, current)
        try:
            credencial = store_signature_reference(
                session,
                usuario_id=usuario_id,
                provedor=payload.provedor,
                external_ref=payload.referencia_externa,
            )
        except UsuarioNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        session.commit()
        session.refresh(credencial)
        return credencial

    @app.get(
        "/usuarios/{usuario_id}/credenciais-assinatura",
        response_model=list[CredencialAssinaturaOut],
    )
    def listar_credenciais_assinatura(
        usuario_id: int,
        session: Session = Depends(get_session),
        current: CurrentUser = Depends(get_current_user),
    ) -> list[models.CredencialAssinatura]:
        get_owned_or_404(session, models.Usuario, usuario_id, current)
        return list_signature_credentials(session, usuario_id=usuario_id)

    @app.patch(
        "/credenciais-assinatura/{credencial_id}/desativar",
        response_model=CredencialAssinaturaOut,
    )
    def desativar_credencial_assinatura(
        credencial_id: int,
        session: Session = Depends(get_session),
        current: CurrentUser = Depends(get_current_user),
    ) -> models.CredencialAssinatura:
        # CredencialAssinatura não tem escritorio_id; valida o tenant pelo usuário dono.
        existente = session.get(models.CredencialAssinatura, credencial_id)
        if existente is not None:
            get_owned_or_404(session, models.Usuario, existente.usuario_id, current)
        try:
            credencial = deactivate_signature_credential(
                session,
                credencial_id=credencial_id,
            )
        except CredencialNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        session.commit()
        session.refresh(credencial)
        return credencial

    @app.get("/court-routing", response_model=CourtRoutingOut)
    def consultar_rota(tribunal: str, grau: str = "1") -> CourtRoutingOut:
        route = resolve_route(tribunal, grau)
        if route is None:
            raise HTTPException(status_code=404, detail="tribunal invalido")
        return CourtRoutingOut(
            sistema=route.sistema,
            url_login=route.url_login,
            url_peticionamento=route.url_peticionamento,
            verificado=route.verificado,
        )

    @app.post(
        "/escritorios/{escritorio_id}/templates-peticao",
        response_model=TemplatePeticaoOut,
    )
    def criar_template_peticao(
        escritorio_id: int,
        payload: TemplatePeticaoCreate,
        session: Session = Depends(get_session),
        current: CurrentUser = Depends(get_current_user),
    ) -> models.TemplatePeticao:
        _require_current_escritorio_path(session, escritorio_id, current)
        template = models.TemplatePeticao(
            escritorio_id=current.escritorio_id,
            tipo=payload.tipo,
            area=payload.area,
            nome=payload.nome,
            conteudo=payload.conteudo,
            ativo=payload.ativo,
        )
        session.add(template)
        session.flush()
        _audit(
            session,
            acao="template_peticao_criado",
            entidade="template_peticao",
            entidade_id=template.id,
            ator_id=current.usuario_id,
            escritorio_id=current.escritorio_id,
            detalhe={"tipo": template.tipo, "area": template.area, "nome": template.nome},
        )
        session.commit()
        session.refresh(template)
        return template

    @app.get(
        "/escritorios/{escritorio_id}/templates-peticao",
        response_model=list[TemplatePeticaoOut],
    )
    def listar_templates_peticao(
        escritorio_id: int,
        ativo: bool | None = Query(default=None),
        tipo: str | None = Query(default=None),
        session: Session = Depends(get_session),
        current: CurrentUser = Depends(get_current_user),
    ) -> list[models.TemplatePeticao]:
        _require_current_escritorio_path(session, escritorio_id, current)
        stmt = tenant_select(models.TemplatePeticao, current)
        if ativo is not None:
            stmt = stmt.where(models.TemplatePeticao.ativo == ativo)
        if tipo is not None:
            stmt = stmt.where(models.TemplatePeticao.tipo == tipo)
        stmt = stmt.order_by(models.TemplatePeticao.id.desc())
        return list(session.scalars(stmt))

    @app.patch(
        "/templates-peticao/{template_id}",
        response_model=TemplatePeticaoOut,
    )
    def atualizar_template_peticao(
        template_id: int,
        payload: TemplatePeticaoUpdate,
        session: Session = Depends(get_session),
        current: CurrentUser = Depends(get_current_user),
    ) -> models.TemplatePeticao:
        template = get_owned_or_404(session, models.TemplatePeticao, template_id, current)
        fields = payload.model_dump(exclude_unset=True)
        for field, value in fields.items():
            setattr(template, field, value)
        _audit(
            session,
            acao="template_peticao_atualizado",
            entidade="template_peticao",
            entidade_id=template.id,
            ator_id=current.usuario_id,
            escritorio_id=template.escritorio_id,
            detalhe={k: v for k, v in fields.items() if k != "conteudo"},
        )
        session.commit()
        session.refresh(template)
        return template

    @app.post("/capture/oab", response_model=CaptureResultOut)
    def capturar_oab(
        payload: CaptureOabRequest,
        background_tasks: BackgroundTasks,
        session: Session = Depends(get_session),
        current: CurrentUser = Depends(get_current_user),
        response: Response = None,
    ) -> CaptureResultOut:
        datajud = DatajudClient() if settings.datajud_api_key else _NoopDatajudClient()
        data_fim = payload.data_fim
        data_inicio = payload.data_inicio
        if data_inicio is None:
            data_fim = data_fim or date.today()
            data_inicio = data_fim - timedelta(days=settings.capture_manual_lookback_days)
        try:
            result = poll_oab(
                session,
                oab=payload.oab,
                uf=payload.uf,
                escritorio_id=current.escritorio_id,
                djen=DjenClient(),
                datajud=datajud,
                calendar=build_calendar(_default_calendar_years()),
                dias_default=payload.dias_default,
                data_inicio=data_inicio,
                data_fim=data_fim,
                # Captura manual roda em modo rápido: só intimações + prazos, sem
                # o loop sequencial de DataJud (rate-limitado pelo CNJ em volume,
                # trava a UI). O processo fica "shell" e é enriquecido on-demand
                # na geração da minuta (draft_from_intimacao). A captura agendada
                # (background/batched) continua enriquecendo.
                enrich=False,
            )
        except Exception as exc:
            session.rollback()
            raise HTTPException(status_code=502, detail=f"captura não concluída: {exc}") from exc

        # DJEN instavel (500/timeout do CNJ em pico): nao descarta o que ja veio.
        # Commita o parcial e sinaliza com 206 + djen_indisponivel=True. O
        # chamador pode retentar depois para pegar o restante das paginas.
        if result.djen_indisponivel and response is not None:
            response.status_code = 206

        # Deduz o sistema (PJe/e-SAJ/...) do tribunal para todo processo do tenant
        # que ainda estava sem — inclui os capturados antes da inferência. Rápido
        # e offline; popula o filtro e o roteamento de protocolo já nesta captura.
        backfill_sistema(session, escritorio_id=current.escritorio_id)
        _audit(
            session,
            acao="captura_oab_executada",
            entidade="escritorio",
            entidade_id=current.escritorio_id,
            ator_id=current.usuario_id,
            escritorio_id=current.escritorio_id,
            detalhe={
                "oab": payload.oab,
                "uf": payload.uf,
                "resultado": result.__dict__,
                "parcial": result.djen_indisponivel,
            },
        )
        session.commit()

        # Enriquecimento roda FORA do request: a captura devolve rápido (só
        # intimações + prazos) e o backfill preenche sistema/classe/órgão dos
        # processos shell em background, no mesmo processo (sem worker separado).
        # Sem DataJud configurado não há o que enriquecer.
        if settings.datajud_api_key:
            background_tasks.add_task(run_enrichment_backfill, current.escritorio_id)

        return CaptureResultOut(**result.__dict__)

    @app.get("/intimacoes", response_model=list[IntimacaoOut])
    def listar_intimacoes(
        session: Session = Depends(get_session),
        current: CurrentUser = Depends(get_current_user),
        processo_id: int | None = Query(default=None),
        limit: int = Query(default=100, le=5000),
    ) -> list[models.Intimacao]:
        stmt = tenant_select(models.Intimacao, current)
        if processo_id is not None:
            stmt = stmt.where(models.Intimacao.processo_id == processo_id)
        stmt = stmt.order_by(models.Intimacao.data_disponibilizacao.desc()).limit(limit)
        return list(session.scalars(stmt))

    @app.get("/review/queue", response_model=list[ReviewQueueItem])
    def fila_revisao(
        session: Session = Depends(get_session),
        current: CurrentUser = Depends(get_current_user),
        limit: int = Query(default=100, le=5000),
    ) -> list[ReviewQueueItem]:
        intimacoes = list(
            session.scalars(
                tenant_select(models.Intimacao, current)
                .order_by(models.Intimacao.data_disponibilizacao.desc())
                .limit(limit)
            )
        )
        processos = {
            item.id: item
            for item in session.scalars(tenant_select(models.Processo, current)).all()
        }
        prazos_por_intimacao: dict[int, models.Prazo] = {}
        for prazo in session.scalars(
            tenant_select(models.Prazo, current).order_by(models.Prazo.data_fatal.asc())
        ):
            if prazo.intimacao_id is not None and prazo.intimacao_id not in prazos_por_intimacao:
                prazos_por_intimacao[prazo.intimacao_id] = prazo

        peticoes_por_prazo: dict[int, models.Peticao] = {}
        peticoes_por_processo: dict[int, models.Peticao] = {}
        for peticao in session.scalars(
            tenant_select(models.Peticao, current).order_by(models.Peticao.id.desc())
        ):
            if peticao.prazo_id is not None and peticao.prazo_id not in peticoes_por_prazo:
                peticoes_por_prazo[peticao.prazo_id] = peticao
            if peticao.processo_id not in peticoes_por_processo:
                peticoes_por_processo[peticao.processo_id] = peticao

        items: list[ReviewQueueItem] = []
        for intimacao in intimacoes:
            prazo = prazos_por_intimacao.get(intimacao.id)
            processo = processos.get(intimacao.processo_id) if intimacao.processo_id else None
            peticao = None
            if prazo is not None:
                peticao = peticoes_por_prazo.get(prazo.id)
            if peticao is None and processo is not None:
                peticao = peticoes_por_processo.get(processo.id)

            items.append(
                ReviewQueueItem(
                    intimacao=IntimacaoOut.model_validate(intimacao),
                    processo=ProcessoOut.model_validate(processo) if processo is not None else None,
                    prazo=PrazoOut.model_validate(prazo) if prazo is not None else None,
                    peticao=PeticaoOut.model_validate(peticao) if peticao is not None else None,
                    status=_status_revisao(prazo, peticao),
                    risco=_risco_prazo(prazo),
                    dias_para_vencer=_dias_para_vencer(prazo),
                )
            )
        return items

    @app.get("/processos", response_model=list[ProcessoOut])
    def listar_processos(
        session: Session = Depends(get_session),
        current: CurrentUser = Depends(get_current_user),
        limit: int = Query(default=100, le=5000),
    ) -> list[models.Processo]:
        stmt = tenant_select(models.Processo, current).order_by(
            models.Processo.id.desc()
        ).limit(limit)
        return list(session.scalars(stmt))

    @app.get("/processos/resumo", response_model=ProcessoResumoLista)
    def listar_processos_resumo(
        session: Session = Depends(get_session),
        current: CurrentUser = Depends(get_current_user),
        limit: int = Query(default=5000, le=5000),
    ) -> ProcessoResumoLista:
        """Lista de processos já cruzada no servidor (próximo prazo + contagens +
        campos de busca) + `total` real. A página de Processos consome isso em vez
        de cruzar 4 listas paginadas no cliente — que subcontava (200 no dashboard
        vs 195 na página, com processos sumindo da tabela). Custo fixo de ~5
        queries agrupadas, sem N+1, independente do número de processos."""
        processos = list(
            session.scalars(
                tenant_select(models.Processo, current)
                .order_by(models.Processo.id.desc())
                .limit(limit)
            )
        )
        total = (
            session.scalar(
                select(func.count())
                .select_from(models.Processo)
                .where(models.Processo.escritorio_id == current.escritorio_id)
            )
            or 0
        )

        # Um scan por tabela relacionada (tenant-scoped), na ordem que define o
        # "mais recente": contagem e tipo representativo saem do mesmo passo.
        intimacoes_count: dict[int, int] = {}
        intimacao_tipo: dict[int, str | None] = {}
        for processo_id, tipo in session.execute(
            select(models.Intimacao.processo_id, models.Intimacao.tipo_comunicacao)
            .where(models.Intimacao.escritorio_id == current.escritorio_id)
            .order_by(models.Intimacao.data_disponibilizacao.desc())
        ).all():
            if processo_id is None:
                continue
            intimacoes_count[processo_id] = intimacoes_count.get(processo_id, 0) + 1
            intimacao_tipo.setdefault(processo_id, tipo)  # 1º na ordem desc = mais recente

        peticoes_count: dict[int, int] = {}
        peticao_tipo: dict[int, str | None] = {}
        for processo_id, tipo in session.execute(
            select(models.Peticao.processo_id, models.Peticao.tipo)
            .where(models.Peticao.escritorio_id == current.escritorio_id)
            .order_by(models.Peticao.id.desc())
        ).all():
            if processo_id is None:
                continue
            peticoes_count[processo_id] = peticoes_count.get(processo_id, 0) + 1
            peticao_tipo.setdefault(processo_id, tipo)

        # Próximo prazo = menor data_fatal entre os pendentes (cumpridos ignorados).
        proximo_prazo: dict[int, models.Prazo] = {}
        for prazo in session.scalars(
            tenant_select(models.Prazo, current)
            .where(models.Prazo.cumprido.is_(False))
            .order_by(models.Prazo.data_fatal.asc())
        ):
            if prazo.processo_id is not None:
                proximo_prazo.setdefault(prazo.processo_id, prazo)

        items = []
        for p in processos:
            prazo = proximo_prazo.get(p.id)
            items.append(
                ProcessoResumoOut(
                    id=p.id,
                    numero=p.numero,
                    classe=p.classe,
                    tribunal=p.tribunal,
                    orgao_julgador=p.orgao_julgador,
                    sistema=p.sistema,
                    intimacoes_count=intimacoes_count.get(p.id, 0),
                    peticoes_count=peticoes_count.get(p.id, 0),
                    proximo_prazo=(
                        ProximoPrazoOut(
                            data_fatal=prazo.data_fatal,
                            cumprido=prazo.cumprido,
                            descricao=prazo.descricao,
                        )
                        if prazo is not None
                        else None
                    ),
                    intimacao_tipo=intimacao_tipo.get(p.id),
                    peticao_tipo=peticao_tipo.get(p.id),
                )
            )
        return ProcessoResumoLista(total=total, items=items)

    @app.get("/prazos", response_model=list[PrazoOut])
    def listar_prazos(
        session: Session = Depends(get_session),
        current: CurrentUser = Depends(get_current_user),
        cumprido: bool | None = Query(default=None),
        limit: int = Query(default=100, le=5000),
    ) -> list[models.Prazo]:
        stmt = tenant_select(models.Prazo, current)
        if cumprido is not None:
            stmt = stmt.where(models.Prazo.cumprido == cumprido)
        stmt = stmt.order_by(models.Prazo.data_fatal.asc()).limit(limit)
        return list(session.scalars(stmt))

    @app.get("/alertas", response_model=list[AlertaPrazo])
    def listar_alertas(
        session: Session = Depends(get_session),
        current: CurrentUser = Depends(get_current_user),
    ) -> list[AlertaPrazo]:
        """Radar de prazo: vencidos, D-0, D-1 e D-3, do mais crítico ao menos.

        A regra vive em ``alertas.radar`` — a mesma que o notificador consome,
        para o e-mail e a tela nunca discordarem sobre o mesmo prazo.
        """
        alertas: list[AlertaPrazo] = []
        for item in prazos_em_alerta(
            session, escritorio_id=current.escritorio_id, hoje=date.today()
        ):
            processo = (
                session.get(models.Processo, item.prazo.processo_id)
                if item.prazo.processo_id is not None
                else None
            )
            alertas.append(
                AlertaPrazo(
                    prazo_id=item.prazo.id,
                    processo_id=item.prazo.processo_id,
                    processo_numero=processo.numero if processo is not None else None,
                    descricao=item.prazo.descricao,
                    data_fatal=item.prazo.data_fatal,
                    dias_para_vencer=item.dias_para_vencer,
                    nivel=item.nivel,
                )
            )
        return alertas

    @app.patch("/prazos/{prazo_id}", response_model=PrazoOut)
    def revisar_prazo(
        prazo_id: int,
        payload: RevisarPrazoRequest,
        session: Session = Depends(get_session),
        current: CurrentUser = Depends(get_current_user),
    ) -> models.Prazo:
        prazo = get_owned_or_404(session, models.Prazo, prazo_id, current)

        fields = payload.model_dump(exclude_unset=True)
        audit_detail = payload.model_dump(mode="json", exclude_unset=True)
        for field, value in fields.items():
            if value is not None:
                setattr(prazo, field, value)

        _audit(
            session,
            acao="prazo_revisado",
            entidade="prazo",
            entidade_id=prazo.id,
            ator_id=current.usuario_id,
            escritorio_id=current.escritorio_id,
            detalhe=audit_detail,
        )
        session.commit()
        session.refresh(prazo)
        return prazo

    @app.post("/prazos/{prazo_id}/cumprir", response_model=PrazoOut)
    def marcar_prazo_cumprido(
        prazo_id: int,
        session: Session = Depends(get_session),
        current: CurrentUser = Depends(get_current_user),
    ) -> models.Prazo:
        prazo = get_owned_or_404(session, models.Prazo, prazo_id, current)
        prazo.cumprido = True
        _audit(
            session,
            acao="prazo_cumprido",
            entidade="prazo",
            entidade_id=prazo.id,
            ator_id=current.usuario_id,
            escritorio_id=current.escritorio_id,
        )
        session.commit()
        session.refresh(prazo)
        return prazo

    @app.get("/peticoes", response_model=list[PeticaoOut])
    def listar_peticoes(
        session: Session = Depends(get_session),
        current: CurrentUser = Depends(get_current_user),
        status: str | None = Query(default=None),
        limit: int = Query(default=100, le=5000),
    ) -> list[models.Peticao]:
        stmt = tenant_select(models.Peticao, current)
        if status is not None:
            stmt = stmt.where(models.Peticao.status == status)
        stmt = stmt.order_by(models.Peticao.id.desc()).limit(limit)
        return list(session.scalars(stmt))

    @app.post("/intimacoes/{intimacao_id}/prazo", response_model=PrazoOut)
    def confirmar_prazo_intimacao(
        intimacao_id: int, payload: ConfirmarPrazoRequest,
        session: Session = Depends(get_session), current: CurrentUser = Depends(get_current_user),
    ):
        from app.prazo_engine.deadline import compute_deadline

        notice = get_owned_or_404(session, models.Intimacao, intimacao_id, current)
        session.execute(select(models.Intimacao.id).where(models.Intimacao.id == notice.id).with_for_update())
        existing = session.scalars(select(models.Prazo).where(
            models.Prazo.intimacao_id == notice.id, models.Prazo.cumprido.is_(False)
        )).first()
        if existing:
            raise HTTPException(409, "Já existe prazo em aberto; revise o prazo vinculado")
        result = compute_deadline(
            payload.data_base, payload.dias, business_days=payload.dias_uteis,
            calendar=build_calendar(range(payload.data_base.year - 1, payload.data_base.year + 17),
                                    extra_holidays=payload.dias_sem_expediente),
        )
        prazo = models.Prazo(
            escritorio_id=current.escritorio_id, processo_id=notice.processo_id,
            intimacao_id=notice.id, descricao=notice.tipo_comunicacao,
            data_inicio=result.data_inicio, data_fatal=result.data_fatal,
            dias=result.dias, dias_uteis=result.dias_uteis, cumprido=False,
        )
        session.add(prazo)
        session.flush()
        drafts = session.scalars(select(models.Peticao).where(
            models.Peticao.escritorio_id == current.escritorio_id,
            models.Peticao.processo_id == notice.processo_id,
            models.Peticao.prazo_id.is_(None),
            models.Peticao.status.in_(["rascunho", "em_revisao"]),
        )).all()
        for draft in drafts:
            if (draft.dossie or {}).get("intimacao_id") == notice.id:
                draft.prazo_id = prazo.id
                draft.dossie = {**draft.dossie, "prazo_revisao_pendente": False}
        _audit(session, acao="prazo_confirmado", entidade="prazo", entidade_id=prazo.id,
               ator_id=current.usuario_id, escritorio_id=current.escritorio_id,
               detalhe={**payload.model_dump(mode="json"), "origem": "revisao_humana", "calendario": "nacional_recesso_civel_com_excecoes_informadas"})
        session.commit()
        return prazo

    @app.post("/intimacoes/{intimacao_id}/draft", response_model=DraftResponse)
    def gerar_minuta(
        intimacao_id: int,
        payload: DraftRequest | None = None,
        session: Session = Depends(get_session),
        current: CurrentUser = Depends(get_current_user),
    ) -> DraftResponse:
        intimacao = get_owned_or_404(session, models.Intimacao, intimacao_id, current)
        payload = payload or DraftRequest()

        calendar = build_calendar(payload.calendar_years or _default_calendar_years())
        datajud_client = DatajudClient() if settings.datajud_api_key else _NoopDatajudClient()
        try:
            prazo, peticao, classificacao = draft_from_intimacao(
                session,
                intimacao,
                calendar=calendar,
                datajud=datajud_client,
                usuario_id=current.usuario_id,
            )
        except MissingIntimationTextError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except DraftContextBudgetError as exc:
            session.rollback()
            raise HTTPException(status_code=422, detail={"code": exc.code, "message": str(exc)}) from exc
        except ContextNotReadyError:
            # Gate fail-closed do contexto: vira 409 estruturado no handler.
            session.rollback()
            raise
        except Exception as exc:  # noqa: BLE001 - classificação/redação via IA pode falhar
            session.rollback()
            raise HTTPException(
                status_code=503,
                detail=f"não foi possível gerar a minuta: {exc}",
            ) from exc

        _audit(
            session,
            acao="minuta_gerada",
            entidade="peticao",
            entidade_id=peticao.id,
            ator_id=current.usuario_id,
            escritorio_id=current.escritorio_id,
            detalhe={
                "intimacao_id": intimacao.id,
                "tipo": classificacao.tipo,
                "peticao_sugerida": classificacao.peticao_sugerida,
                "confianca": classificacao.confianca,
            },
        )
        session.commit()
        return DraftResponse(
            prazo=PrazoOut.model_validate(prazo) if prazo else None,
            peticao=PeticaoOut.model_validate(peticao),
            classificacao=classificacao.model_dump(),
        )

    @app.patch("/peticoes/{peticao_id}", response_model=PeticaoOut)
    def editar_peticao(
        peticao_id: int,
        payload: EditPeticaoRequest,
        session: Session = Depends(get_session),
        current: CurrentUser = Depends(get_current_user),
    ) -> models.Peticao:
        peticao = get_owned_or_404(session, models.Peticao, peticao_id, current)
        if peticao.status in {"protocolada", "protocolando"}:
            raise HTTPException(
                status_code=409, detail="petição em envio ou protocolada não pode ser editada"
            )

        alteracoes: dict = {}
        if payload.conteudo is not None and payload.conteudo != peticao.conteudo:
            peticao.conteudo = payload.conteudo
            alteracoes["conteudo"] = True
            if peticao.status == "aprovada":
                peticao.status = "em_revisao"
                peticao.aprovada_por = None
                alteracoes["aprovacao_invalidada"] = True
        if payload.status is not None and payload.status != peticao.status:
            alteracoes["status"] = {"de": peticao.status, "para": payload.status}
            peticao.status = payload.status

        if alteracoes:
            if "conteudo" in alteracoes or "status" in alteracoes:
                dossie = dict(peticao.dossie or {})
                dossie.pop("pdf_snapshot", None)
                peticao.dossie = dossie
                peticao.aprovada_por = None
            _audit(
                session,
                acao="peticao_editada",
                entidade="peticao",
                entidade_id=peticao.id,
                ator_id=current.usuario_id,
                escritorio_id=current.escritorio_id,
                detalhe={"tipo": peticao.tipo, "alteracoes": alteracoes},
            )
        session.commit()
        session.refresh(peticao)
        return peticao

    @app.post("/peticoes/{peticao_id}/approve", response_model=PeticaoOut)
    def aprovar_peticao(
        peticao_id: int,
        session: Session = Depends(get_session),
        current: CurrentUser = Depends(get_current_user),
    ) -> models.Peticao:
        peticao = get_owned_or_404(session, models.Peticao, peticao_id, current)
        # Same process lock as represented-client changes; approvals and relinking serialize.
        session.execute(select(models.Processo.id).where(models.Processo.id == peticao.processo_id).with_for_update())
        session.refresh(peticao)
        if peticao.status in {"protocolada", "protocolando"}:
            raise HTTPException(status_code=409, detail="petição em envio ou já protocolada")
        from app.filing.approval import approve_snapshot

        snapshot = approve_snapshot(session, peticao)
        peticao.status = "aprovada"
        peticao.aprovada_por = current.usuario_id
        _audit(
            session,
            acao="peticao_aprovada",
            entidade="peticao",
            entidade_id=peticao.id,
            ator_id=current.usuario_id,
            escritorio_id=current.escritorio_id,
            detalhe={"tipo": peticao.tipo, "pdf_sha256": snapshot["pdf_sha256"],
                     "input_sha256": snapshot["input_sha256"]},
        )
        session.commit()
        session.refresh(peticao)
        return peticao

    @app.post("/peticoes/{peticao_id}/protocolar/async", response_model=JobOut)
    def protocolar_peticao_async(
        peticao_id: int,
        payload: ProtocolarAsyncRequest | None = None,
        session: Session = Depends(get_session),
        current: CurrentUser = Depends(get_current_user),
    ) -> models.JobExecucao:
        get_owned_or_404(session, models.Peticao, peticao_id, current)
        credencial_id = payload.credencial_id if payload is not None else None
        try:
            # Roteia qualquer sistema pelo driver (sandbox na demo; PJe real no
            # piloto). A sessao do tribunal e resolvida no cofre por usuario_id.
            datajud_client = DatajudClient() if settings.datajud_api_key else _NoopDatajudClient()
            job = run_pje_protocol_job(
                session,
                peticao_id,
                credencial_id=credencial_id,
                usuario_id=current.usuario_id,
                datajud=datajud_client,
                submit=True,
            )
        except (PeticaoNotFoundError, CredencialNaoEncontradaError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ProcessoSemOrgaoError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except (
            AlreadyFiledError,
            ApprovalRequiredError,
            CredencialInativaError,
            UnsupportedFilingSystemError,
        ) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

        session.commit()
        session.refresh(job)
        return job

    @app.post("/peticoes/{peticao_id}/protocolar/confirmar", response_model=PeticaoOut)
    def confirmar_protocolo_peticao(
        peticao_id: int,
        payload: ConfirmarProtocoloRequest,
        session: Session = Depends(get_session),
        current: CurrentUser = Depends(get_current_user),
    ) -> models.Peticao:
        get_owned_or_404(session, models.Peticao, peticao_id, current)
        try:
            peticao = confirm_manual_protocol(
                session,
                peticao_id,
                protocolo=payload.protocolo,
                comprovante_uri=payload.comprovante_uri,
                credencial_id=payload.credencial_id,
                usuario_id=current.usuario_id,
            )
        except PeticaoNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (AlreadyFiledError, ApprovalRequiredError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

        session.commit()
        session.refresh(peticao)
        return peticao

    @app.get("/peticoes/{peticao_id}/pdf")
    def baixar_peticao_pdf(
        peticao_id: int,
        session: Session = Depends(get_session),
        current: CurrentUser = Depends(get_current_user),
    ) -> Response:
        """Preview da peça final: o mesmo PDF (timbrado incluso) que o job de
        protocolo anexa, renderizado sob demanda para o gate humano."""
        peticao = get_owned_or_404(session, models.Peticao, peticao_id, current)
        processo = session.get(models.Processo, peticao.processo_id)
        from app.filing.approval import prepare_snapshot, snapshot_pdf, ApprovalSnapshotError

        try:
            if peticao.status not in {"aprovada", "protocolada", "protocolando"}:
                prepare_snapshot(session, peticao)
            pdf = snapshot_pdf(session, peticao, require_approved=peticao.status in {"aprovada", "protocolada", "protocolando"}, validate_current=peticao.status != "protocolada")
        except ApprovalSnapshotError as exc:
            raise HTTPException(409, str(exc)) from exc
        session.commit()
        nome_arquivo = f"minuta-{processo.numero if processo else peticao.id}.pdf"
        return Response(
            content=pdf,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{nome_arquivo}"'},
        )

    @app.post("/chat", response_model=ChatResponse)
    def chat(
        payload: ChatRequest,
        session: Session = Depends(get_session),
        current: CurrentUser = Depends(get_current_user),
    ) -> ChatResponse:
        contexto = None
        if payload.processo_id is not None:
            proc = get_owned_or_404(session, models.Processo, payload.processo_id, current)
            if proc is not None:
                contexto = {
                    "numero": proc.numero,
                    "classe": proc.classe,
                    "tribunal": proc.tribunal,
                    "orgao_julgador": proc.orgao_julgador,
                    "sistema": proc.sistema,
                }
        try:
            result = chat_with_assistant(
                [m.model_dump() for m in payload.messages],
                session=session,
                contexto_processo=contexto,
            )
        except Exception as exc:  # noqa: BLE001 - chamada de IA pode falhar
            raise HTTPException(
                status_code=503,
                detail=f"assistente indisponível: {exc}",
            ) from exc
        return ChatResponse(**result)

    return app


app = create_app()
