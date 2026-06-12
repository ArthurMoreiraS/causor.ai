"""FastAPI application — read-only views over the SOR.

These endpoints are intentionally read-only. Any irreversible action
(drafting/filing) goes through the agent + human-approval gate, never a plain
REST write here.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.assistant import chat_with_assistant
from app.agent.service import MissingIntimationTextError, draft_from_intimacao
from app.api.schemas import (
    AuditLogOut,
    ApprovePeticaoRequest,
    CaptureOabRequest,
    CaptureResultOut,
    ChatRequest,
    ChatResponse,
    CreateCredencialAssinaturaRequest,
    CredencialAssinaturaOut,
    DraftRequest,
    DraftResponse,
    EditPeticaoRequest,
    IntimacaoOut,
    JobOut,
    MarcarPrazoCumpridoRequest,
    OperationalDashboard,
    PeticaoOut,
    PrazoOut,
    ProcessoOut,
    RevisarPrazoRequest,
    ReviewQueueItem,
    TemplatePeticaoCreate,
    TemplatePeticaoOut,
    TemplatePeticaoUpdate,
)
from app.capture.datajud import DatajudClient, ProcessoDTO
from app.capture.djen import DjenClient
from app.capture.poll import poll_oab
from app.prazo_engine.factory import build_calendar
from app.queue.jobs import (
    AlreadyFiledError,
    ApprovalRequiredError,
    JobNotFoundError,
    PeticaoNotFoundError,
    create_job,
    get_job,
    run_fake_protocol_job,
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


def _resolve_escritorio(session: Session, escritorio_id: int | None) -> models.Escritorio:
    if escritorio_id is not None:
        escritorio = session.get(models.Escritorio, escritorio_id)
        if escritorio is None:
            raise HTTPException(status_code=404, detail="escritório não encontrado")
        return escritorio

    escritorio = session.scalar(select(models.Escritorio).order_by(models.Escritorio.id.asc()))
    if escritorio is not None:
        return escritorio

    raise HTTPException(
        status_code=400,
        detail="Nenhum escritório cadastrado. Informe escritorio_id ou cadastre um escritório real.",
    )


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


def create_app() -> FastAPI:
    app = FastAPI(title="Causor API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/dashboard/operational", response_model=OperationalDashboard)
    def dashboard_operacional(session: Session = Depends(get_session)) -> OperationalDashboard:
        processos = len(session.scalars(select(models.Processo.id)).all())
        intimacoes = len(session.scalars(select(models.Intimacao.id)).all())
        prazos = list(session.scalars(select(models.Prazo)).all())
        peticoes = list(session.scalars(select(models.Peticao)).all())
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
        entidade: str | None = Query(default=None),
        entidade_id: int | None = Query(default=None),
        limit: int = Query(default=100, le=500),
    ) -> list[models.AuditLog]:
        stmt = select(models.AuditLog)
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
    ) -> models.JobExecucao:
        escritorio = _resolve_escritorio(session, payload.escritorio_id)
        job = create_job(
            session,
            tipo="captura_oab",
            entidade="escritorio",
            entidade_id=escritorio.id,
            payload={
                **payload.model_dump(mode="json"),
                "escritorio_id": escritorio.id,
            },
        )
        session.commit()
        session.refresh(job)
        return job

    @app.get("/jobs/{job_id}", response_model=JobOut)
    def consultar_job(
        job_id: int,
        session: Session = Depends(get_session),
    ) -> models.JobExecucao:
        try:
            return get_job(session, job_id)
        except JobNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post(
        "/usuarios/{usuario_id}/credenciais-assinatura",
        response_model=CredencialAssinaturaOut,
    )
    def cadastrar_credencial_assinatura(
        usuario_id: int,
        payload: CreateCredencialAssinaturaRequest,
        session: Session = Depends(get_session),
    ) -> models.CredencialAssinatura:
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
    ) -> list[models.CredencialAssinatura]:
        return list_signature_credentials(session, usuario_id=usuario_id)

    @app.patch(
        "/credenciais-assinatura/{credencial_id}/desativar",
        response_model=CredencialAssinaturaOut,
    )
    def desativar_credencial_assinatura(
        credencial_id: int,
        session: Session = Depends(get_session),
    ) -> models.CredencialAssinatura:
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
        "/escritorios/{escritorio_id}/templates-peticao",
        response_model=TemplatePeticaoOut,
    )
    def criar_template_peticao(
        escritorio_id: int,
        payload: TemplatePeticaoCreate,
        session: Session = Depends(get_session),
    ) -> models.TemplatePeticao:
        if session.get(models.Escritorio, escritorio_id) is None:
            raise HTTPException(status_code=404, detail="escritorio nao encontrado")
        template = models.TemplatePeticao(
            escritorio_id=escritorio_id,
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
            escritorio_id=escritorio_id,
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
    ) -> list[models.TemplatePeticao]:
        stmt = select(models.TemplatePeticao).where(
            models.TemplatePeticao.escritorio_id == escritorio_id
        )
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
    ) -> models.TemplatePeticao:
        template = session.get(models.TemplatePeticao, template_id)
        if template is None:
            raise HTTPException(status_code=404, detail="template nao encontrado")
        fields = payload.model_dump(exclude_unset=True)
        for field, value in fields.items():
            setattr(template, field, value)
        _audit(
            session,
            acao="template_peticao_atualizado",
            entidade="template_peticao",
            entidade_id=template.id,
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
    ) -> CaptureResultOut:
        escritorio = _resolve_escritorio(session, payload.escritorio_id)
        datajud = DatajudClient() if settings.datajud_api_key else _NoopDatajudClient()
        try:
            result = poll_oab(
                session,
                oab=payload.oab,
                uf=payload.uf,
                escritorio_id=escritorio.id,
                djen=DjenClient(),
                datajud=datajud,
                calendar=build_calendar(_default_calendar_years()),
                dias_default=payload.dias_default,
                data_inicio=payload.data_inicio,
                data_fim=payload.data_fim,
            )
        except Exception as exc:
            session.rollback()
            raise HTTPException(status_code=502, detail=f"captura não concluída: {exc}") from exc

        _audit(
            session,
            acao="captura_oab_executada",
            entidade="escritorio",
            entidade_id=escritorio.id,
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
        processo_id: int | None = Query(default=None),
        limit: int = Query(default=100, le=500),
    ) -> list[models.Intimacao]:
        stmt = select(models.Intimacao)
        if processo_id is not None:
            stmt = stmt.where(models.Intimacao.processo_id == processo_id)
        stmt = stmt.order_by(models.Intimacao.data_disponibilizacao.desc()).limit(limit)
        return list(session.scalars(stmt))

    @app.get("/review/queue", response_model=list[ReviewQueueItem])
    def fila_revisao(
        session: Session = Depends(get_session),
        limit: int = Query(default=100, le=500),
    ) -> list[ReviewQueueItem]:
        intimacoes = list(
            session.scalars(
                select(models.Intimacao)
                .order_by(models.Intimacao.data_disponibilizacao.desc())
                .limit(limit)
            )
        )
        processos = {item.id: item for item in session.scalars(select(models.Processo)).all()}
        prazos_por_intimacao: dict[int, models.Prazo] = {}
        for prazo in session.scalars(select(models.Prazo).order_by(models.Prazo.data_fatal.asc())):
            if prazo.intimacao_id is not None and prazo.intimacao_id not in prazos_por_intimacao:
                prazos_por_intimacao[prazo.intimacao_id] = prazo

        peticoes_por_prazo: dict[int, models.Peticao] = {}
        peticoes_por_processo: dict[int, models.Peticao] = {}
        for peticao in session.scalars(select(models.Peticao).order_by(models.Peticao.id.desc())):
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
        limit: int = Query(default=100, le=500),
    ) -> list[models.Processo]:
        stmt = select(models.Processo).order_by(models.Processo.id.desc()).limit(limit)
        return list(session.scalars(stmt))

    @app.get("/prazos", response_model=list[PrazoOut])
    def listar_prazos(
        session: Session = Depends(get_session),
        cumprido: bool | None = Query(default=None),
        limit: int = Query(default=100, le=500),
    ) -> list[models.Prazo]:
        stmt = select(models.Prazo)
        if cumprido is not None:
            stmt = stmt.where(models.Prazo.cumprido == cumprido)
        stmt = stmt.order_by(models.Prazo.data_fatal.asc()).limit(limit)
        return list(session.scalars(stmt))

    @app.patch("/prazos/{prazo_id}", response_model=PrazoOut)
    def revisar_prazo(
        prazo_id: int,
        payload: RevisarPrazoRequest,
        session: Session = Depends(get_session),
    ) -> models.Prazo:
        prazo = session.get(models.Prazo, prazo_id)
        if prazo is None:
            raise HTTPException(status_code=404, detail="prazo não encontrado")

        fields = payload.model_dump(exclude_unset=True, exclude={"usuario_id"})
        audit_detail = payload.model_dump(
            mode="json",
            exclude_unset=True,
            exclude={"usuario_id"},
        )
        for field, value in fields.items():
            if value is not None:
                setattr(prazo, field, value)

        _audit(
            session,
            acao="prazo_revisado",
            entidade="prazo",
            entidade_id=prazo.id,
            ator_id=payload.usuario_id,
            detalhe=audit_detail,
        )
        session.commit()
        session.refresh(prazo)
        return prazo

    @app.post("/prazos/{prazo_id}/cumprir", response_model=PrazoOut)
    def marcar_prazo_cumprido(
        prazo_id: int,
        payload: MarcarPrazoCumpridoRequest,
        session: Session = Depends(get_session),
    ) -> models.Prazo:
        prazo = session.get(models.Prazo, prazo_id)
        if prazo is None:
            raise HTTPException(status_code=404, detail="prazo não encontrado")
        prazo.cumprido = True
        _audit(
            session,
            acao="prazo_cumprido",
            entidade="prazo",
            entidade_id=prazo.id,
            ator_id=payload.usuario_id,
        )
        session.commit()
        session.refresh(prazo)
        return prazo

    @app.get("/peticoes", response_model=list[PeticaoOut])
    def listar_peticoes(
        session: Session = Depends(get_session),
        status: str | None = Query(default=None),
        limit: int = Query(default=100, le=500),
    ) -> list[models.Peticao]:
        stmt = select(models.Peticao)
        if status is not None:
            stmt = stmt.where(models.Peticao.status == status)
        stmt = stmt.order_by(models.Peticao.id.desc()).limit(limit)
        return list(session.scalars(stmt))

    @app.post("/intimacoes/{intimacao_id}/draft", response_model=DraftResponse)
    def gerar_minuta(
        intimacao_id: int,
        payload: DraftRequest,
        session: Session = Depends(get_session),
    ) -> DraftResponse:
        intimacao = session.get(models.Intimacao, intimacao_id)
        if intimacao is None:
            raise HTTPException(status_code=404, detail="intimação não encontrada")

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
    ) -> models.Peticao:
        peticao = session.get(models.Peticao, peticao_id)
        if peticao is None:
            raise HTTPException(status_code=404, detail="petição não encontrada")
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
                ator_id=payload.usuario_id,
                detalhe={"tipo": peticao.tipo, "alteracoes": alteracoes},
            )
        session.commit()
        session.refresh(peticao)
        return peticao

    @app.post("/peticoes/{peticao_id}/approve", response_model=PeticaoOut)
    def aprovar_peticao(
        peticao_id: int,
        payload: ApprovePeticaoRequest,
        session: Session = Depends(get_session),
    ) -> models.Peticao:
        peticao = session.get(models.Peticao, peticao_id)
        if peticao is None:
            raise HTTPException(status_code=404, detail="petição não encontrada")
        if peticao.status == "protocolada":
            raise HTTPException(status_code=409, detail="petição já protocolada")
        peticao.status = "aprovada"
        peticao.aprovada_por = payload.usuario_id
        _audit(
            session,
            acao="peticao_aprovada",
            entidade="peticao",
            entidade_id=peticao.id,
            ator_id=payload.usuario_id,
            detalhe={"tipo": peticao.tipo},
        )
        session.commit()
        session.refresh(peticao)
        return peticao

    @app.post("/peticoes/{peticao_id}/protocolar", response_model=PeticaoOut)
    def marcar_protocolada(
        peticao_id: int,
        session: Session = Depends(get_session),
    ) -> models.Peticao:
        peticao = session.get(models.Peticao, peticao_id)
        if peticao is None:
            raise HTTPException(status_code=404, detail="petição não encontrada")
        if peticao.status != "aprovada":
            raise HTTPException(status_code=409, detail="aprovação obrigatória antes do protocolo")
        peticao.status = "protocolada"
        peticao.protocolada_em = datetime.now(timezone.utc)
        _audit(
            session,
            acao="peticao_protocolada",
            entidade="peticao",
            entidade_id=peticao.id,
            ator_id=peticao.aprovada_por,
            detalhe={"tipo": peticao.tipo},
        )
        session.commit()
        session.refresh(peticao)
        return peticao

    @app.post("/peticoes/{peticao_id}/protocolar/async", response_model=JobOut)
    def protocolar_peticao_async(
        peticao_id: int,
        session: Session = Depends(get_session),
    ) -> models.JobExecucao:
        try:
            job = run_fake_protocol_job(session, peticao_id)
        except PeticaoNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except AlreadyFiledError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ApprovalRequiredError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

        session.commit()
        session.refresh(job)
        return job

    @app.post("/chat", response_model=ChatResponse)
    def chat(
        payload: ChatRequest,
        session: Session = Depends(get_session),
    ) -> ChatResponse:
        contexto = None
        if payload.processo_id is not None:
            proc = session.get(models.Processo, payload.processo_id)
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
