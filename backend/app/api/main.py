"""FastAPI application — read-only views over the SOR.

These endpoints are intentionally read-only. Any irreversible action
(drafting/filing) goes through the agent + human-approval gate, never a plain
REST write here.
"""

from __future__ import annotations

import base64
import binascii
import logging
import re
from datetime import date, datetime, timedelta, timezone

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.orm import Session

from app.agent.assistant import chat_with_assistant
from app.agent.service import MissingIntimationTextError, draft_from_intimacao
from app.agent.context_selection import DraftContextBudgetError
from app.alertas.radar import prazos_em_alerta
from app.auth.jwt_auth import CurrentUser, get_current_user
from app.auth.papeis import exigir, permissoes_de, requer
from app.auth.tenant import get_owned_or_404, tenant_select
from app.api.schemas import (
    AlertaPrazo,
    AuditLogOut,
    CaptureOabRequest,
    CaptureResultOut,
    ChatRequest,
    ChatResponse,
    ConfirmarPrazoRequest,
    DraftRequest,
    DraftResponse,
    EditPeticaoRequest,
    IntimacaoOut,
    IntimacaoAnalysisOut,
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
    RevisarPrazoRequest,
    ReviewQueueItem,
    TemplatePeticaoCreate,
    TemplatePeticaoOut,
    TemplatePeticaoUpdate,
    UsuarioOut,
)
from app.api.read_models import (
    deadline_statement, notice_statement, operational_counts, read_deadlines, read_notices,
)
from app.capture.datajud import DatajudClient, ProcessoDTO
from app.capture.djen import DjenClient
from app.capture.enrich import backfill_sistema, run_enrichment_backfill
from app.capture.poll import poll_oab
from app.filing.timbrado import LogoInvalidoError, normalize_logo
from app.prazo_engine.factory import build_calendar
from app.prazo_engine.pipeline import KEY, enqueue_analysis, memory, set_memory
from app.queue.jobs import (
    JobNotFoundError,
    create_job,
    get_job,
)
from app.settings import settings
from app.sor import models
from app.sor.db import get_session
from app.autos.context import ContextNotReadyError


def _default_calendar_years() -> list[int]:
    year = datetime.now(timezone.utc).year
    return [year - 1, year, year + 1]


def _normalizar_oab(oab: str, uf: str) -> tuple[str, str]:
    numero = re.sub(r"[\s.\-/]", "", oab).upper()
    estado = uf.strip().upper()
    if not numero or len(numero) > 20 or not numero.isalnum():
        raise HTTPException(status_code=422, detail="numero da OAB invalido")
    if len(estado) != 2 or not estado.isalpha():
        raise HTTPException(status_code=422, detail="UF da OAB invalida")
    return numero, estado


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


def _dias_para_vencer(prazo: models.Prazo | PrazoOut | None) -> int | None:
    if prazo is None:
        return None
    from zoneinfo import ZoneInfo

    today = datetime.now(ZoneInfo("America/Sao_Paulo")).date()
    return (prazo.data_fatal - today).days


def _risco_prazo(prazo: models.Prazo | PrazoOut | None) -> str:
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
    prazo: models.Prazo | PrazoOut | None,
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
        if prazo.revisao_status not in ("confirmado", "calculado_a_revisar"):
            return "prazo_a_revisar"
        return "prazo_calculado"
    return "capturada"


def _payload_matches_oab(payload: dict | None, *, oab: str, uf: str) -> bool:
    if not isinstance(payload, dict):
        return False
    oab_key = re.sub(r"[\s.\-/]", "", oab).upper()
    uf_upper = uf.upper()
    for source in payload.get("_causor_oabs") or []:
        if isinstance(source, dict) and source.get("oab") == oab and source.get("uf") == uf_upper:
            return True
    for item in payload.get("destinatarioadvogados") or []:
        if not isinstance(item, dict):
            continue
        advogado = item.get("advogado")
        if not isinstance(advogado, dict):
            continue
        numero = re.sub(r"[\s.\-/]", "", str(advogado.get("numero_oab") or "")).upper()
        item_uf = str(advogado.get("uf_oab") or "").upper()
        if numero == oab_key and item_uf == uf_upper:
            return True
    return False


def _job_matches_oab(job: models.JobExecucao, *, oab: str, uf: str) -> bool:
    payload = job.payload if isinstance(job.payload, dict) else {}
    return (
        re.sub(r"[\s.\-/]", "", str(payload.get("oab") or "")).upper()
        == re.sub(r"[\s.\-/]", "", oab).upper()
        and str(payload.get("uf") or "").upper() == uf.upper()
    )


def _purge_oab_data(
    session: Session,
    *,
    escritorio_id: int,
    oab: str,
    uf: str,
    preserve_authored: bool = False,
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
    if preserve_authored:
        candidates = {item.processo_id for item in intimacoes
                      if item.id in target_intimacao_ids and item.processo_id is not None}
        list(session.scalars(select(models.Processo.id).where(
            models.Processo.id.in_(candidates), models.Processo.escritorio_id == escritorio_id,
        ).with_for_update()))
        other_oabs = list(session.scalars(select(models.OabMonitorada).where(
            models.OabMonitorada.escritorio_id == escritorio_id,
            models.OabMonitorada.ativo.is_(True),
            or_(models.OabMonitorada.oab != oab, models.OabMonitorada.uf != uf),
        )))
        protected_processes = set()
        for model in (models.TrabalhoJuridico, models.Peticao, models.Documento, models.Tarefa):
            protected_processes.update(session.scalars(select(model.processo_id).where(
                model.processo_id.in_(candidates))))
        retained = {item.id for item in intimacoes if item.id in target_intimacao_ids and (
            item.processo_id in protected_processes or memory(item).get("status") == "confirmado"
            or any(_payload_matches_oab(item.payload, oab=other.oab, uf=other.uf) for other in other_oabs)
        )}
        target_intimacao_ids -= retained
        counts["intimacoes_preservadas"] = len(retained)
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
    if preserve_authored:
        # Keep the cancelled request identity so a delayed retry cannot restart it.
        for job in session.scalars(select(models.JobExecucao).where(models.JobExecucao.id.in_(job_ids))):
            if job.tipo == "captura_oab":
                job.status = "failed"
                job.erro = "Monitoramento removido pelo usuário"
                job.resultado = {"cancelada_por_remocao": True}
                job.payload = {**(job.payload or {}), "removida": True}
        counts["capturas_canceladas"] = sum(1 for job in session.scalars(select(models.JobExecucao).where(
            models.JobExecucao.id.in_(job_ids))) if job.tipo == "captura_oab")
        job_ids = [job.id for job in session.scalars(select(models.JobExecucao).where(
            models.JobExecucao.id.in_(job_ids))) if job.tipo != "captura_oab"]
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


def purge_untracked_process(session: Session, *, escritorio_id: int, processo_id: int) -> dict[str, int] | None:
    """Remove um processo capturado que ninguém mais acompanha.

    Vale só para processo que veio da captura (tem intimação) e que, depois de
    excluído um trabalho, ficou sem nada do escritório: sem trabalho, minuta,
    documento ou tarefa, sem prazo confirmado e sem intimação de OAB ainda
    monitorada. São as mesmas proteções da remoção de OAB. Processo cadastrado à
    mão, sem intimação, fica. Não commita; a auditoria é mantida.
    """
    process = session.get(models.Processo, processo_id)
    if process is None or process.escritorio_id != escritorio_id:
        return None
    notices = list(session.scalars(select(models.Intimacao).where(
        models.Intimacao.escritorio_id == escritorio_id, models.Intimacao.processo_id == processo_id)))
    if not notices:
        return None
    for model in (models.TrabalhoJuridico, models.Peticao, models.Documento, models.Tarefa):
        if session.scalar(select(model.id).where(model.processo_id == processo_id).limit(1)) is not None:
            return None
    active = list(session.scalars(select(models.OabMonitorada).where(
        models.OabMonitorada.escritorio_id == escritorio_id, models.OabMonitorada.ativo.is_(True))))
    for notice in notices:
        if memory(notice).get("status") == "confirmado":
            return None
        if any(_payload_matches_oab(notice.payload, oab=oab.oab, uf=oab.uf) for oab in active):
            return None

    from app.capture.cleanup import purge_process

    return purge_process(session, escritorio_id=escritorio_id, processo_id=processo_id)


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

    from app.api.autos_routes import router as autos_router
    from app.api.mni_routes import router as mni_router
    from app.api.office_routes import router as office_router

    app.include_router(autos_router)
    app.include_router(mni_router)
    app.include_router(office_router)
    from app.api.work_routes import router as work_router
    app.include_router(work_router)
    from app.api.document_routes import router as document_router
    app.include_router(document_router)
    from app.api.equipe_routes import router as equipe_router
    app.include_router(equipe_router)

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
            papel=current.papel,
            permissoes=permissoes_de(current.papel),
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
        campos_do_escritorio = {
            "nome_escritorio", "cnpj", "timbrado_cabecalho", "timbrado_rodape", "timbrado_logo",
        }
        if campos_do_escritorio & payload.model_dump(exclude_none=True).keys():
            exigir(current, "configurar_escritorio")

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
        from zoneinfo import ZoneInfo
        today = datetime.now(ZoneInfo("America/Sao_Paulo")).date()
        counts = operational_counts(session, current, today)

        return OperationalDashboard(
            metrics=[
                {"key": "processos", "label": "Processos monitorados", "value": counts["processos"]},
                {"key": "intimacoes", "label": "Intimações capturadas", "value": counts["intimacoes"]},
                {"key": "prazos", "label": "Prazos pendentes", "value": counts["prazos"]},
                {"key": "prazos_a_revisar", "label": "Prazos a revisar", "value": counts["prazos_a_revisar"]},
                {"key": "risco", "label": "Alto risco", "value": counts["risco"]},
                {"key": "vencidos", "label": "Prazos vencidos", "value": counts["vencidos"]},
                {
                    "key": "minutas",
                    "label": "Minutas em revisao",
                    "value": counts["minutas"],
                },
                {
                    "key": "aprovadas",
                    "label": "Minutas aprovadas",
                    "value": counts["aprovadas"],
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
                    "detail": "Rota a validar por tribunal",
                    "status": "planned",
                },
            ],
            connectors=[
                {
                    "key": "djen",
                    "name": "DJEN",
                    "detail": "captura oficial de comunicações",
                    "status": "implemented",
                },
                {
                    "key": "datajud",
                    "name": "DataJud",
                    "detail": "metadados e andamentos processuais",
                    "status": "implemented",
                },
                {
                    "key": "pje",
                    "name": "PJe",
                    "detail": "rota específica por tribunal, ainda sem homologação",
                    "status": "validation",
                },
                {
                    "key": "esaj",
                    "name": "e-SAJ",
                    "detail": "rota judicial não homologada",
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
        current: CurrentUser = Depends(requer("configurar_escritorio")),
    ) -> models.JobExecucao:
        # Cadastro e job sao uma transacao; lock no escritorio serializa pedidos
        # concorrentes pela mesma OAB em PostgreSQL.
        session.scalar(
            select(models.Escritorio.id)
            .where(models.Escritorio.id == current.escritorio_id)
            .with_for_update()
        )
        oab_numero, uf = _normalizar_oab(payload.oab, payload.uf)
        if payload.request_id:
            prior = session.scalars(
                select(models.JobExecucao).where(
                    models.JobExecucao.tipo == "captura_oab",
                    or_(
                        and_(models.JobExecucao.entidade == "escritorio",
                             models.JobExecucao.entidade_id == current.escritorio_id),
                        and_(models.JobExecucao.entidade == "oab_monitorada",
                             models.JobExecucao.entidade_id.in_(
                                 select(models.OabMonitorada.id).where(
                                     models.OabMonitorada.escritorio_id == current.escritorio_id,
                                 )
                             )),
                    ),
                ).order_by(models.JobExecucao.id.desc())
            )
            for existing in prior:
                previous = existing.payload or {}
                request_ids = [previous.get("request_id"), *(previous.get("request_ids") or [])]
                if payload.request_id in request_ids:
                    if not (
                        (existing.entidade == "escritorio" and existing.entidade_id == current.escritorio_id)
                        or (
                            existing.entidade == "oab_monitorada"
                            and existing.entidade_id is not None
                            and (monitor := session.get(models.OabMonitorada, existing.entidade_id)) is not None
                            and monitor.escritorio_id == current.escritorio_id
                        )
                    ):
                        continue
                    if previous.get("oab") != oab_numero or previous.get("uf") != uf:
                        raise HTTPException(status_code=409, detail="identificador ja usado para outra OAB")
                    return existing
        cadastro = session.scalar(
            select(models.OabMonitorada).where(
                models.OabMonitorada.escritorio_id == current.escritorio_id,
                models.OabMonitorada.oab == oab_numero,
                models.OabMonitorada.uf == uf,
            )
        )
        if cadastro is None:
            cadastro = models.OabMonitorada(
                escritorio_id=current.escritorio_id, oab=oab_numero,
                uf=uf, intervalo_horas=12, ativo=True,
            )
            session.add(cadastro)
            session.flush()
        else:
            cadastro.ativo = True

        active = session.scalars(
            select(models.JobExecucao).where(
                models.JobExecucao.tipo == "captura_oab",
                models.JobExecucao.status.in_(("queued", "running")),
                models.JobExecucao.entidade_id.in_((current.escritorio_id, cadastro.id)),
            ).order_by(models.JobExecucao.id.desc())
        )
        for existing in active:
            if existing.entidade == "escritorio" and existing.entidade_id != current.escritorio_id:
                continue
            if existing.entidade == "oab_monitorada" and existing.entidade_id != cadastro.id:
                continue
            if existing.entidade not in ("escritorio", "oab_monitorada"):
                continue
            previous = existing.payload or {}
            if (str(previous.get("oab", "")).strip().upper(), str(previous.get("uf", "")).strip().upper()) == (oab_numero, uf):
                if payload.request_id and payload.request_id != previous.get("request_id"):
                    existing.payload = {
                        **previous,
                        "request_ids": [*(previous.get("request_ids") or []), payload.request_id],
                    }
                session.commit()
                session.refresh(existing)
                return existing
        # Sem janela no payload, quem executar o job varre o histórico inteiro da
        # OAB no DJEN. O default limitado é gravado aqui, no momento da criação,
        # para que o executor não dependa de o chamador lembrar de repassá-lo.
        dados = payload.model_dump(mode="json")
        dados["oab"] = oab_numero
        dados["uf"] = uf
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
            payload={**dados, "escritorio_id": current.escritorio_id, "oab_monitorada_id": cadastro.id, "enrich": False},
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
        current: CurrentUser = Depends(requer("configurar_escritorio")),
    ) -> models.OabMonitorada:
        oab_numero, uf = _normalizar_oab(payload.oab, payload.uf)
        existing = session.scalar(
            select(models.OabMonitorada).where(
                models.OabMonitorada.escritorio_id == current.escritorio_id,
                models.OabMonitorada.oab == oab_numero,
                models.OabMonitorada.uf == uf,
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
            oab=oab_numero,
            uf=uf,
            intervalo_horas=payload.intervalo_horas,
            ativo=True,
        )
        session.add(oab)
        session.commit()
        session.refresh(oab)
        return oab

    @app.post("/capturas/oab/remover-dados", response_model=OabRemovalResultOut)
    def remover_dados_oab(
        payload: OabMonitoradaCreate, session: Session = Depends(get_session),
        current: CurrentUser = Depends(requer("configurar_escritorio")),
    ) -> OabRemovalResultOut:
        oab_numero, uf = _normalizar_oab(payload.oab, payload.uf)
        session.scalar(select(models.Escritorio.id).where(
            models.Escritorio.id == current.escritorio_id).with_for_update())
        # Serialize with a capture window before selecting the records to remove.
        jobs = list(session.scalars(select(models.JobExecucao).where(
            models.JobExecucao.tipo == "captura_oab").order_by(models.JobExecucao.id)))
        for job in jobs:
            if ((job.payload or {}).get("escritorio_id") == current.escritorio_id
                    and _job_matches_oab(job, oab=oab_numero, uf=uf)):
                session.scalar(select(models.JobExecucao.id).where(
                    models.JobExecucao.id == job.id).with_for_update())
        registration = session.scalar(select(models.OabMonitorada).where(
            models.OabMonitorada.escritorio_id == current.escritorio_id,
            models.OabMonitorada.oab == oab_numero, models.OabMonitorada.uf == uf,
        ))
        registration_id = registration.id if registration else None
        counts = _purge_oab_data(session, escritorio_id=current.escritorio_id,
                                oab=oab_numero, uf=uf, preserve_authored=True)
        if registration:
            session.delete(registration)
        _audit(session, acao="oab_dados_removidos", entidade="escritorio",
               entidade_id=current.escritorio_id, ator_id=current.usuario_id,
               escritorio_id=current.escritorio_id,
               detalhe={"oab": oab_numero, "uf": uf, "counts": counts,
                        "auditoria_preservada": True})
        session.commit()
        return OabRemovalResultOut(oab_id=registration_id, oab=oab_numero, uf=uf,
                                   purge=True, removidos=counts)

    @app.delete("/capturas/oab/{oab_id}", response_model=OabRemovalResultOut)
    def remover_oab_monitorada(
        oab_id: int,
        purge: bool = Query(default=True),
        session: Session = Depends(get_session),
        current: CurrentUser = Depends(requer("configurar_escritorio")),
    ) -> OabRemovalResultOut:
        # Same order as enqueue: office first, then jobs/registration. Removal
        # must not race a scheduler creating a new job after the purge snapshot.
        session.scalar(select(models.Escritorio.id).where(
            models.Escritorio.id == current.escritorio_id).with_for_update())
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
        current: CurrentUser = Depends(requer("configurar_escritorio")),
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

    @app.get("/intimacoes/analise-status", response_model=list[IntimacaoAnalysisOut])
    def estados_analise_intimacoes(
        ids: list[int] = Query(min_length=1, max_length=200),
        session: Session = Depends(get_session),
        current: CurrentUser = Depends(get_current_user),
    ) -> list[IntimacaoAnalysisOut]:
        stmt = notice_statement(current).with_only_columns(
            models.Intimacao.id, models.Intimacao.payload[KEY].label("prazo_analise"),
        ).where(models.Intimacao.id.in_(ids)).order_by(models.Intimacao.id)
        return [IntimacaoAnalysisOut(
            id=row.id, prazo_analise=row.prazo_analise if isinstance(row.prazo_analise, dict) else None,
        ) for row in session.execute(stmt)]

    @app.get("/intimacoes", response_model=list[IntimacaoOut])
    def listar_intimacoes(
        session: Session = Depends(get_session),
        current: CurrentUser = Depends(get_current_user),
        processo_id: int | None = Query(default=None),
        limit: int = Query(default=100, le=5000),
    ) -> list[IntimacaoOut]:
        stmt = notice_statement(current)
        if processo_id is not None:
            stmt = stmt.where(models.Intimacao.processo_id == processo_id)
        stmt = stmt.order_by(models.Intimacao.data_disponibilizacao.desc()).limit(limit)
        return read_notices(session, stmt)

    @app.get("/review/queue", response_model=list[ReviewQueueItem])
    def fila_revisao(
        session: Session = Depends(get_session),
        current: CurrentUser = Depends(get_current_user),
        limit: int = Query(default=100, le=5000),
    ) -> list[ReviewQueueItem]:
        intimacoes = read_notices(
            session,
            notice_statement(current)
            .order_by(models.Intimacao.data_disponibilizacao.desc())
            .limit(limit),
        )
        processos = {
            item.id: item
            for item in session.scalars(tenant_select(models.Processo, current)).all()
        }
        prazos_por_intimacao: dict[int, PrazoOut] = {}
        for prazo in read_deadlines(session,
            deadline_statement(current).order_by(models.Prazo.data_fatal.asc())
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
                    status=((intimacao.prazo_analise or {}).get("status", "capturada")
                            if prazo is None and peticao is None else _status_revisao(prazo, peticao)),
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
        proximo_prazo: dict[int, PrazoOut] = {}
        for prazo in read_deadlines(session,
            deadline_statement(current)
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
                            revisao_status=prazo.revisao_status,
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
    ) -> list[PrazoOut]:
        stmt = deadline_statement(current)
        if cumprido is not None:
            stmt = stmt.where(models.Prazo.cumprido == cumprido)
        stmt = stmt.order_by(models.Prazo.data_fatal.asc()).limit(limit)
        return read_deadlines(session, stmt)

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
                    revisao_status=item.prazo.revisao_status,
                )
            )
        return alertas

    @app.patch("/prazos/{prazo_id}", response_model=PrazoOut)
    def revisar_prazo(
        prazo_id: int,
        payload: RevisarPrazoRequest,
        session: Session = Depends(get_session),
        current: CurrentUser = Depends(requer("decidir_prazo")),
    ) -> models.Prazo:
        prazo = get_owned_or_404(session, models.Prazo, prazo_id, current)

        fields = payload.model_dump(exclude_unset=True)
        audit_detail = payload.model_dump(mode="json", exclude_unset=True)
        first_counted_day = None
        if any(key in fields for key in ("data_inicio", "dias", "dias_uteis")):
            from app.prazo_engine.deadline import compute_deadline
            from app.prazo_engine.djen import compute_djen_civil_deadline
            from app.prazo_engine.calendar import ForensicCalendar

            base = fields.get("data_inicio") or prazo.data_inicio
            days = fields.get("dias") or prazo.dias
            business = fields.get("dias_uteis") if fields.get("dias_uteis") is not None else prazo.dias_uteis
            notice = session.get(models.Intimacao, prazo.intimacao_id) if prazo.intimacao_id else None
            previous_memory = memory(notice) if notice else {}
            exceptions = previous_memory.get("dias_sem_expediente", []) if previous_memory.get("prazo_id") == prazo.id else []
            calendar = build_calendar(range(base.year - 1, base.year + 19),
                                      extra_holidays=[date.fromisoformat(day) for day in exceptions])
            first_counted_day = calendar.next_business_day(base) if business else base + timedelta(days=1)
            if notice and notice.fonte == "DJEN" and notice.data_disponibilizacao and business:
                publication_calendar = ForensicCalendar(holidays=calendar._holidays)
                fields["data_fatal"] = compute_djen_civil_deadline(
                    notice.data_disponibilizacao, days, publication_calendar=publication_calendar,
                    counting_calendar=calendar, publication=base,
                ).data_fatal
            else:
                fields["data_fatal"] = compute_deadline(
                    base, days, calendar=calendar, business_days=business,
                ).data_fatal
            audit_detail["data_fatal_recalculada"] = fields["data_fatal"].isoformat()
        for field, value in fields.items():
            if value is not None:
                setattr(prazo, field, value)
        if prazo.intimacao_id:
            notice = session.get(models.Intimacao, prazo.intimacao_id)
            if notice and notice.escritorio_id == current.escritorio_id:
                before = memory(notice)
                if before.get("prazo_id") == prazo.id:
                    set_memory(notice, {**before, "status": "confirmado" if before.get("status") == "confirmado" else "calculado_a_revisar",
                                        "publicacao": prazo.data_inicio.isoformat(), "dias": prazo.dias,
                                        "unidade": "dias_uteis" if prazo.dias_uteis else "dias_corridos",
                                        "data_fatal": prazo.data_fatal.isoformat(),
                                        **({"primeiro_dia": first_counted_day.isoformat()} if first_counted_day else {}),
                                        "motivo": "Contagem confirmada pelo advogado" if before.get("status") == "confirmado" else "Revise calendário e suspensões locais antes de confirmar"})
                    audit_detail["memoria_anterior"] = before
                    audit_detail["memoria_posterior"] = memory(notice)

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
        current: CurrentUser = Depends(requer("decidir_prazo")),
    ) -> models.Prazo:
        # Cumprir é ato humano e não depende de conferência: prazo calculado
        # automaticamente já vale (decisão de 07/10/2026).
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

    @app.post("/intimacoes/analisar-prazos")
    def analisar_intimacoes_existentes(
        session: Session = Depends(get_session), current: CurrentUser = Depends(get_current_user),
        after_id: int = Query(default=0, ge=0), limit: int = Query(default=100, ge=1, le=500),
    ) -> dict:
        notices = list(session.scalars(
            tenant_select(models.Intimacao, current)
            .where(models.Intimacao.id > after_id)
            .order_by(models.Intimacao.id).limit(limit)
        ))
        queued = 0
        for notice in notices:
            if enqueue_analysis(session, notice) is not None:
                queued += 1
        session.commit()
        return {"enfileiradas": queued, "ultimo_id": notices[-1].id if notices else after_id,
                "ha_mais": len(notices) == limit}

    @app.post("/intimacoes/{intimacao_id}/analisar-prazo")
    def tentar_analise_prazo(
        intimacao_id: int, session: Session = Depends(get_session),
        current: CurrentUser = Depends(get_current_user),
    ) -> dict:
        notice = get_owned_or_404(session, models.Intimacao, intimacao_id, current)
        if memory(notice).get("status") != "falha":
            raise HTTPException(409, "Somente uma análise com falha pode ser repetida")
        job = enqueue_analysis(session, notice, retry=True)
        session.commit()
        return {"job_id": job.id if job else None}

    @app.post("/intimacoes/{intimacao_id}/prazo", response_model=PrazoOut)
    def confirmar_prazo_intimacao(
        intimacao_id: int, payload: ConfirmarPrazoRequest,
        session: Session = Depends(get_session), current: CurrentUser = Depends(requer("decidir_prazo")),
    ):
        from app.prazo_engine.deadline import compute_deadline
        from app.prazo_engine.djen import compute_djen_civil_deadline
        from app.prazo_engine.calendar import ForensicCalendar

        notice = get_owned_or_404(session, models.Intimacao, intimacao_id, current)
        session.execute(select(models.Intimacao.id).where(models.Intimacao.id == notice.id).with_for_update())
        session.refresh(notice)
        existing_rows = list(session.scalars(select(models.Prazo).where(
            models.Prazo.escritorio_id == current.escritorio_id,
            models.Prazo.intimacao_id == notice.id,
        ).with_for_update()))
        if len(existing_rows) > 1:
            raise HTTPException(409, "Há múltiplos prazos vinculados; revise cada prazo antes de confirmar")
        existing = existing_rows[0] if existing_rows else None
        previous_memory = memory(notice)
        if existing and previous_memory.get("status") == "confirmado":
            same = (previous_memory.get("prazo_id") == existing.id
                    and existing.data_inicio == payload.data_base
                    and existing.dias == payload.dias
                    and existing.dias_uteis == payload.dias_uteis
                    and previous_memory.get("dias_sem_expediente", []) ==
                    [d.isoformat() for d in payload.dias_sem_expediente])
            if same:
                return existing
        if existing and (existing.cumprido or previous_memory.get("status") == "confirmado"):
            raise HTTPException(409, "Já existe prazo em aberto; revise o prazo vinculado")
        calendar = build_calendar(range(payload.data_base.year - 1, payload.data_base.year + 19),
                                  extra_holidays=payload.dias_sem_expediente)
        if notice.fonte == "DJEN" and notice.data_disponibilizacao and payload.dias_uteis:
            result = compute_djen_civil_deadline(
                notice.data_disponibilizacao, payload.dias,
                publication_calendar=ForensicCalendar(holidays=calendar._holidays),
                counting_calendar=calendar, publication=payload.data_base,
            )
            fatal = result.data_fatal
            base = result.publicacao
        else:
            result = compute_deadline(payload.data_base, payload.dias,
                                      business_days=payload.dias_uteis, calendar=calendar)
            fatal = result.data_fatal
            base = result.data_inicio
        prazo = existing or models.Prazo(
            escritorio_id=current.escritorio_id, processo_id=notice.processo_id,
            intimacao_id=notice.id, descricao=notice.tipo_comunicacao,
            cumprido=False,
        )
        prazo.data_inicio = base
        prazo.data_fatal = fatal
        prazo.dias = payload.dias
        prazo.dias_uteis = payload.dias_uteis
        if payload.descricao and payload.descricao.strip():
            prazo.descricao = payload.descricao.strip()
        if existing is None:
            session.add(prazo)
        session.flush()
        set_memory(notice, {**previous_memory, "status": "confirmado", "prazo_id": prazo.id,
                            "publicacao": base.isoformat(), "dias": payload.dias,
                            "primeiro_dia": (calendar.next_business_day(base) if payload.dias_uteis else base + timedelta(days=1)).isoformat(),
                            "unidade": "dias_uteis" if payload.dias_uteis else "dias_corridos",
                            "dias_sem_expediente": [d.isoformat() for d in payload.dias_sem_expediente],
                            "justificativa_humana": payload.justificativa,
                            "data_fatal": prazo.data_fatal.isoformat(),
                            "motivo": "Contagem confirmada pelo advogado"})
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
               detalhe={**payload.model_dump(mode="json"), "origem": "revisao_humana", "calendario": "nacional_recesso_civel_com_excecoes_informadas", "memoria_anterior": previous_memory, "memoria_posterior": memory(notice)})
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
        session.execute(select(models.Processo.id).where(models.Processo.id == peticao.processo_id).with_for_update())
        session.refresh(peticao)
        work_id = (peticao.dossie or {}).get("trabalho_id")
        if work_id:
            active = session.scalar(select(models.TentativaProtocolo.id).join(models.PacoteProtocolo).where(
                models.PacoteProtocolo.trabalho_id == work_id,
                models.TentativaProtocolo.status.not_in(["cancelado", "falha_confirmada"])).limit(1))
            if active:
                raise HTTPException(409, "Existe uma tentativa de envio. Reconcilie o resultado antes de alterar a minuta.")
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
                dossie["revisao_conteudo"] = dossie.get("revisao_conteudo", 0) + 1
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
        current: CurrentUser = Depends(requer("aprovar_minuta")),
    ) -> models.Peticao:
        peticao = get_owned_or_404(session, models.Peticao, peticao_id, current)
        # Same process lock as represented-client changes; approvals and relinking serialize.
        session.execute(select(models.Processo.id).where(models.Processo.id == peticao.processo_id).with_for_update())
        session.refresh(peticao)
        if peticao.status in {"protocolada", "protocolando"}:
            raise HTTPException(status_code=409, detail="petição em envio ou já protocolada")
        from app.filing.approval import approve_snapshot

        try:
            snapshot = approve_snapshot(session, peticao)
        except ValueError as exc:
            session.rollback()
            raise HTTPException(409, str(exc)) from exc
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
        work = get_owned_or_404(session, models.TrabalhoJuridico, payload.trabalho_id, current) if payload.trabalho_id else None
        if work and payload.processo_id and work.processo_id != payload.processo_id:
            raise HTTPException(422, "Trabalho e processo não correspondem")
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
            from app.agent.chat_tools import execute_scoped_read_tool
            result = chat_with_assistant(
                [m.model_dump() for m in payload.messages],
                session=session,
                contexto_processo=contexto,
                resumo_contexto=f"Trabalho em foco: #{work.id}. Consulte consultar_trabalho antes de responder sobre documentos ou ações." if work else None,
                read_tool_runner=lambda db, name, args: execute_scoped_read_tool(db, name, args, current=current, work_id=work.id if work else None),
            )
        except Exception as exc:  # noqa: BLE001 - chamada de IA pode falhar
            raise HTTPException(
                status_code=503,
                detail="Assistente indisponível. Tente novamente; nenhuma ação foi confirmada automaticamente.",
            ) from exc
        return ChatResponse(**result)

    return app


app = create_app()
