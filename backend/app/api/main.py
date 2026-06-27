"""FastAPI application — read-only views over the SOR.

These endpoints are intentionally read-only. Any irreversible action
(drafting/filing) goes through the agent + human-approval gate, never a plain
REST write here.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.agent.assistant import chat_with_assistant
from app.agent.service import MissingIntimationTextError, draft_from_intimacao
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
    CreateCredencialAssinaturaRequest,
    CreatePjeSessionRequest,
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
from app.capture.poll import poll_oab
from app.prazo_engine.factory import build_calendar
from app.queue.jobs import (
    AlreadyFiledError,
    ApprovalRequiredError,
    CredencialInativaError,
    CredencialNaoEncontradaError,
    JobNotFoundError,
    PeticaoNotFoundError,
    UnsupportedFilingSystemError,
    create_job,
    get_job,
    confirm_manual_protocol,
    run_fake_protocol_job,
    run_pje_assisted_protocol_job,
)
from app.settings import settings
from app.sor import models
from app.sor.db import get_session
from app.vault.service import (
    CredencialNotFoundError,
    UsuarioNotFoundError,
    VaultProviderError,
    deactivate_signature_credential,
    list_signature_credentials,
    store_pje_session_reference,
    store_signature_reference,
)


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


def _audit_matches_oab_or_entities(
    audit: models.AuditLog,
    *,
    oab: str,
    uf: str,
    entity_ids: dict[str, set[int]],
) -> bool:
    detalhe = audit.detalhe if isinstance(audit.detalhe, dict) else {}
    if (
        "".join(ch for ch in str(detalhe.get("oab") or "") if ch.isdigit())
        == "".join(ch for ch in oab if ch.isdigit())
        and str(detalhe.get("uf") or "").upper() == uf.upper()
    ):
        return True
    if audit.entidade and audit.entidade_id is not None:
        return audit.entidade_id in entity_ids.get(audit.entidade, set())
    return False


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
    if not target_intimacao_ids:
        return counts

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

    if target_peticao_ids:
        counts["documentos"] += session.execute(
            delete(models.Documento).where(models.Documento.peticao_id.in_(target_peticao_ids))
        ).rowcount or 0
    if target_process_ids:
        counts["documentos"] += session.execute(
            delete(models.Documento).where(models.Documento.processo_id.in_(target_process_ids))
        ).rowcount or 0
        counts["andamentos"] = session.execute(
            delete(models.Andamento).where(models.Andamento.processo_id.in_(target_process_ids))
        ).rowcount or 0

    entity_ids = {
        "intimacao": target_intimacao_ids,
        "prazo": target_prazo_ids,
        "peticao": target_peticao_ids,
        "processo": target_process_ids,
    }
    audit_ids = [
        audit.id
        for audit in session.scalars(
            select(models.AuditLog).where(models.AuditLog.escritorio_id == escritorio_id)
        )
        if _audit_matches_oab_or_entities(audit, oab=oab, uf=uf, entity_ids=entity_ids)
    ]
    if audit_ids:
        counts["auditoria"] = session.execute(
            delete(models.AuditLog).where(models.AuditLog.id.in_(audit_ids))
        ).rowcount or 0

    job_ids = [
        job.id
        for job in session.scalars(select(models.JobExecucao))
        if _job_matches_oab(job, oab=oab, uf=uf)
        or (job.entidade in entity_ids and job.entidade_id in entity_ids[job.entidade])
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


def create_app() -> FastAPI:
    app = FastAPI(title="Causor API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
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

        return OperationalDashboard(
            metrics=[
                {"key": "processos", "label": "Processos monitorados", "value": processos},
                {"key": "intimacoes", "label": "Intimações capturadas", "value": intimacoes},
                {"key": "prazos", "label": "Prazos pendentes", "value": len(pending_deadlines)},
                {"key": "risco", "label": "Alto risco", "value": len(high_risk)},
                {
                    "key": "minutas",
                    "label": "Minutas em revisao",
                    "value": len([p for p in peticoes if p.status == "rascunho"]),
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
        job = create_job(
            session,
            tipo="captura_oab",
            entidade="escritorio",
            entidade_id=current.escritorio_id,
            payload={
                **payload.model_dump(mode="json"),
                "escritorio_id": current.escritorio_id,
            },
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

    @app.post(
        "/usuarios/{usuario_id}/pje-sessoes",
        response_model=CredencialAssinaturaOut,
    )
    def cadastrar_sessao_pje(
        usuario_id: int,
        payload: CreatePjeSessionRequest,
        session: Session = Depends(get_session),
        current: CurrentUser = Depends(get_current_user),
    ) -> models.CredencialAssinatura:
        get_owned_or_404(session, models.Usuario, usuario_id, current)
        try:
            credencial = store_pje_session_reference(
                session,
                usuario_id=usuario_id,
                tribunal=payload.tribunal,
                url_base=payload.url_base,
                storage_state=payload.storage_state,
            )
        except UsuarioNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except VaultProviderError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        session.commit()
        session.refresh(credencial)
        return credencial

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
        session: Session = Depends(get_session),
        current: CurrentUser = Depends(get_current_user),
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
            )
        except Exception as exc:
            session.rollback()
            raise HTTPException(status_code=502, detail=f"captura não concluída: {exc}") from exc

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
            },
        )
        session.commit()
        return CaptureResultOut(**result.__dict__)

    @app.get("/intimacoes", response_model=list[IntimacaoOut])
    def listar_intimacoes(
        session: Session = Depends(get_session),
        current: CurrentUser = Depends(get_current_user),
        processo_id: int | None = Query(default=None),
        limit: int = Query(default=100, le=500),
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
        limit: int = Query(default=100, le=500),
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
        limit: int = Query(default=100, le=500),
    ) -> list[models.Processo]:
        stmt = tenant_select(models.Processo, current).order_by(
            models.Processo.id.desc()
        ).limit(limit)
        return list(session.scalars(stmt))

    @app.get("/prazos", response_model=list[PrazoOut])
    def listar_prazos(
        session: Session = Depends(get_session),
        current: CurrentUser = Depends(get_current_user),
        cumprido: bool | None = Query(default=None),
        limit: int = Query(default=100, le=500),
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
        """Radar de prazo: vencidos, D-0, D-1 e D-3, do mais crítico ao menos."""
        today = date.today()
        stmt = (
            tenant_select(models.Prazo, current)
            .where(models.Prazo.cumprido.is_(False))
            .where(models.Prazo.data_fatal <= today + timedelta(days=3))
            .order_by(models.Prazo.data_fatal.asc())
        )
        alertas: list[AlertaPrazo] = []
        for prazo in session.scalars(stmt):
            dias = (prazo.data_fatal - today).days
            nivel = "vencido" if dias < 0 else "d0" if dias == 0 else "d1" if dias == 1 else "d3"
            processo = (
                session.get(models.Processo, prazo.processo_id)
                if prazo.processo_id is not None
                else None
            )
            alertas.append(
                AlertaPrazo(
                    prazo_id=prazo.id,
                    processo_id=prazo.processo_id,
                    processo_numero=processo.numero if processo is not None else None,
                    descricao=prazo.descricao,
                    data_fatal=prazo.data_fatal,
                    dias_para_vencer=dias,
                    nivel=nivel,
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
        limit: int = Query(default=100, le=500),
    ) -> list[models.Peticao]:
        stmt = tenant_select(models.Peticao, current)
        if status is not None:
            stmt = stmt.where(models.Peticao.status == status)
        stmt = stmt.order_by(models.Peticao.id.desc()).limit(limit)
        return list(session.scalars(stmt))

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
        try:
            prazo, peticao, classificacao = draft_from_intimacao(
                session, intimacao, calendar=calendar
            )
        except MissingIntimationTextError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
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
            prazo=PrazoOut.model_validate(prazo),
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
        if peticao.status == "protocolada":
            raise HTTPException(
                status_code=409, detail="petição protocolada não pode ser editada"
            )

        alteracoes: dict = {}
        if payload.conteudo is not None:
            peticao.conteudo = payload.conteudo
            alteracoes["conteudo"] = True
        if payload.status is not None and payload.status != peticao.status:
            alteracoes["status"] = {"de": peticao.status, "para": payload.status}
            peticao.status = payload.status

        if alteracoes:
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
        if peticao.status == "protocolada":
            raise HTTPException(status_code=409, detail="petição já protocolada")
        peticao.status = "aprovada"
        peticao.aprovada_por = current.usuario_id
        _audit(
            session,
            acao="peticao_aprovada",
            entidade="peticao",
            entidade_id=peticao.id,
            ator_id=current.usuario_id,
            escritorio_id=current.escritorio_id,
            detalhe={"tipo": peticao.tipo},
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
        peticao = get_owned_or_404(session, models.Peticao, peticao_id, current)
        credencial_id = payload.credencial_id if payload is not None else None
        try:
            if (peticao.processo.sistema or "").strip().lower() == "pje":
                job = run_pje_assisted_protocol_job(
                    session,
                    peticao_id,
                    credencial_id=credencial_id,
                )
            else:
                job = run_fake_protocol_job(session, peticao_id, credencial_id=credencial_id)
        except (PeticaoNotFoundError, CredencialNaoEncontradaError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
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
            )
        except PeticaoNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (AlreadyFiledError, ApprovalRequiredError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

        session.commit()
        session.refresh(peticao)
        return peticao

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
