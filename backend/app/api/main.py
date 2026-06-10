"""FastAPI application — read-only views over the SOR.

These endpoints are intentionally read-only. Any irreversible action
(drafting/filing) goes through the agent + human-approval gate, never a plain
REST write here.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.service import MissingIntimationTextError, draft_from_intimacao
from app.api.schemas import (
    ApprovePeticaoRequest,
    CaptureDemoRequest,
    CaptureOabRequest,
    CaptureResultOut,
    DraftRequest,
    DraftResponse,
    IntimacaoOut,
    MarcarPrazoCumpridoRequest,
    OperationalDashboard,
    PeticaoOut,
    PrazoOut,
    ProcessoOut,
    RevisarPrazoRequest,
    ReviewQueueItem,
)
from app.capture.datajud import DatajudClient, ProcessoDTO
from app.capture.djen import ComunicacaoDTO, DjenClient
from app.capture.poll import poll_oab
from app.prazo_engine.factory import build_calendar
from app.settings import settings
from app.sor import models
from app.sor.db import get_session


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

    escritorio = models.Escritorio(nome="Causor Demo Advocacia", cnpj="00000000000100")
    session.add(escritorio)
    session.flush()
    return escritorio


class _NoopDatajudClient:
    def consultar_processo(self, numero_processo: str, *, tribunal: str) -> ProcessoDTO | None:
        return None


class _DemoDjenClient:
    def consultar(self, oab: str, uf: str, **_: object) -> list[ComunicacaoDTO]:
        today = date.today()
        return [
            ComunicacaoDTO.from_item(
                {
                    "id": f"demo-capture-{today.isoformat()}",
                    "numero_processo": "1009988-77.2026.8.26.0100",
                    "siglaTribunal": "TJSP",
                    "tipoComunicacao": "Intimação para réplica",
                    "nomeOrgao": "3a Vara Civel",
                    "texto": (
                        "Fica a parte autora intimada para apresentar réplica no prazo legal, "
                        f"vinculada à OAB {oab}/{uf}."
                    ),
                    "data_disponibilizacao": today.isoformat(),
                }
            )
        ]


class _DemoDatajudClient:
    def consultar_processo(self, numero_processo: str, *, tribunal: str) -> ProcessoDTO | None:
        return ProcessoDTO.from_source(
            {
                "numeroProcesso": numero_processo,
                "classe": {"nome": "Procedimento Comum Civel"},
                "tribunal": tribunal,
                "orgaoJulgador": {"nome": "3a Vara Civel"},
                "sistema": {"nome": "e-SAJ"},
                "dataAjuizamento": "2026-02-10T00:00:00.000Z",
                "movimentos": [
                    {
                        "codigo": 51,
                        "nome": "Conclusos para despacho",
                        "dataHora": "2026-05-20T12:00:00.000Z",
                    }
                ],
            }
        )


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

    @app.post("/capture/demo", response_model=CaptureResultOut)
    def capturar_demo(
        payload: CaptureDemoRequest,
        session: Session = Depends(get_session),
    ) -> CaptureResultOut:
        escritorio = _resolve_escritorio(session, payload.escritorio_id)
        result = poll_oab(
            session,
            oab="123456",
            uf="SP",
            escritorio_id=escritorio.id,
            djen=_DemoDjenClient(),
            datajud=_DemoDatajudClient(),
            calendar=build_calendar(_default_calendar_years()),
            dias_default=payload.dias_default,
        )
        _audit(
            session,
            acao="captura_demo_executada",
            entidade="escritorio",
            entidade_id=escritorio.id,
            detalhe=result.__dict__,
        )
        session.commit()
        return CaptureResultOut(**result.__dict__)

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
        session.commit()
        return DraftResponse(
            prazo=PrazoOut.model_validate(prazo),
            peticao=PeticaoOut.model_validate(peticao),
            classificacao=classificacao.model_dump(),
        )

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
        session.commit()
        session.refresh(peticao)
        return peticao

    return app


app = create_app()
