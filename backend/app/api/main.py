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

from app.agent.service import MissingIntimationTextError, draft_from_intimacao
from app.api.schemas import (
    ApprovePeticaoRequest,
    DraftRequest,
    DraftResponse,
    IntimacaoOut,
    OperationalDashboard,
    PeticaoOut,
    PrazoOut,
    ProcessoOut,
)
from app.prazo_engine.factory import build_calendar
from app.sor import models
from app.sor.db import get_session


def _default_calendar_years() -> list[int]:
    year = datetime.now(timezone.utc).year
    return [year - 1, year, year + 1]


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
