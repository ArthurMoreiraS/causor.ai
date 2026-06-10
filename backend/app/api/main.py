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
            raise HTTPException(status_code=404, detail="intimacao not found")

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
            raise HTTPException(status_code=404, detail="peticao not found")
        if peticao.status == "protocolada":
            raise HTTPException(status_code=409, detail="peticao already filed")
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
            raise HTTPException(status_code=404, detail="peticao not found")
        if peticao.status != "aprovada":
            raise HTTPException(status_code=409, detail="approval required before filing")
        peticao.status = "protocolada"
        peticao.protocolada_em = datetime.now(timezone.utc)
        session.commit()
        session.refresh(peticao)
        return peticao

    return app


app = create_app()
