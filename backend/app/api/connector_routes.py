"""Endpoints de acesso aos tribunais (login unificado via agente).

O advogado dispara o login pelo Causor; o agente pareado abre o portal na
máquina dele. Aqui só circulam rota resolvida e estado derivado — nunca
cookie, senha ou certificado.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.jwt_auth import CurrentUser, get_current_user
from app.autos.context import latest_context
from app.capture.court_routing import resolve_route
from app.connectors import sessions as court_sessions
from app.connectors.assistant import resolve_next_step
from app.connectors.coverage import coverage_status, known_profiles
from app.sor import models
from app.sor.db import get_session

router = APIRouter(tags=["connectors"])


class ProximoPassoOut(BaseModel):
    processo_id: int
    ready: bool
    next_step: str | None
    rota: dict


@router.get("/processos/{processo_id}/contexto/proximo-passo", response_model=ProximoPassoOut)
def proximo_passo(
    processo_id: int,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(get_current_user),
) -> ProximoPassoOut:
    processo = session.get(models.Processo, processo_id)
    if processo is None or processo.escritorio_id != current.escritorio_id:
        raise HTTPException(status_code=404, detail="processo nao encontrado")
    contexto = latest_context(session, processo=processo)
    ready = contexto is not None and contexto.status == "ready"
    next_step, rota = resolve_next_step(
        session, processo=processo, context_ready=ready
    )
    return ProximoPassoOut(
        processo_id=processo.id, ready=ready, next_step=next_step, rota=rota
    )


class CoverageRowOut(BaseModel):
    profile_key: str
    sistema: str
    tribunal: str
    grau: str
    state: str
    reasons: list[str]
    read_autos: bool
    prepare_filing: bool
    submit_filing: bool
    last_validation_at: datetime | None


def _coverage_rows(session: Session) -> list[CoverageRowOut]:
    rows: list[CoverageRowOut] = []
    for profile in known_profiles():
        status = coverage_status(session, profile=profile)
        rows.append(
            CoverageRowOut(
                profile_key=profile.key,
                sistema=profile.sistema,
                tribunal=profile.tribunal,
                grau=profile.grau,
                state=status.state,
                reasons=status.reasons,
                read_autos=profile.capabilities.read_autos,
                prepare_filing=profile.capabilities.prepare_filing,
                submit_filing=profile.capabilities.submit_filing,
                last_validation_at=status.last_validation_at,
            )
        )
    return rows


@router.get("/connectors/coverage", response_model=list[CoverageRowOut])
def listar_cobertura(
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(get_current_user),  # noqa: ARG001 - exige auth
) -> list[CoverageRowOut]:
    return _coverage_rows(session)


@router.get("/connectors/coverage/{profile_key}", response_model=CoverageRowOut)
def detalhar_cobertura(
    profile_key: str,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(get_current_user),  # noqa: ARG001 - exige auth
) -> CoverageRowOut:
    for row in _coverage_rows(session):
        if row.profile_key == profile_key:
            return row
    raise HTTPException(status_code=404, detail="perfil de conector nao encontrado")


class CourtLoginIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    grau: str = "1"
    sistema: str | None = None  # confirmação/correção manual da rota resolvida


class CourtLoginOut(BaseModel):
    sistema: str
    tribunal: str
    grau: str
    status: str
    command_id: int


class SessaoRotaOut(BaseModel):
    sistema: str
    tribunal: str
    grau: str
    status: str
    version_marker: str | None
    last_confirmed_at: datetime | None
    last_error_code: str | None


class SessaoOut(BaseModel):
    processo_id: int
    rotas: list[SessaoRotaOut]


def _get_owned_processo(
    session: Session, processo_id: int, current: CurrentUser
) -> models.Processo:
    processo = session.get(models.Processo, processo_id)
    if processo is None or processo.escritorio_id != current.escritorio_id:
        raise HTTPException(status_code=404, detail="processo nao encontrado")
    return processo


def _resolve_instancia(
    session: Session, processo: models.Processo, *, sistema: str, tribunal: str, grau: str
) -> models.ProcessoInstancia | None:
    return session.scalars(
        select(models.ProcessoInstancia).where(
            models.ProcessoInstancia.processo_id == processo.id,
            models.ProcessoInstancia.sistema == sistema,
            models.ProcessoInstancia.tribunal == tribunal,
            models.ProcessoInstancia.grau == grau,
        )
    ).first()


@router.post("/processos/{processo_id}/tribunal/login", response_model=CourtLoginOut)
def login_tribunal(
    processo_id: int,
    payload: CourtLoginIn | None = None,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(get_current_user),
) -> CourtLoginOut:
    processo = _get_owned_processo(session, processo_id, current)
    grau = (payload.grau if payload else "1") or "1"
    if grau not in {"1", "2"}:
        raise HTTPException(status_code=422, detail="grau deve ser '1' ou '2'")
    if not processo.tribunal:
        raise HTTPException(
            status_code=422, detail="processo sem tribunal; complete o cadastro"
        )

    route = resolve_route(processo.tribunal, grau)
    # O sistema da instância é autoritativo (casos migrados); depois vem a
    # confirmação manual do advogado; o registro é o palpite final.
    sistema = (
        (payload.sistema if payload else None)
        or processo.sistema
        or (route.sistema if route else None)
        or "DESCONHECIDO"
    )
    url_login = route.url_login if route and route.sistema == sistema else None
    if route and not url_login and route.sistema != sistema:
        corrected = resolve_route(processo.tribunal, grau)
        url_login = corrected.url_login if corrected else None
    if not url_login:
        raise HTTPException(
            status_code=422,
            detail=(
                f"tribunal {processo.tribunal} sem URL de login no registro para "
                f"{sistema}; verifique o cadastro"
            ),
        )

    instancia = _resolve_instancia(
        session, processo, sistema=sistema, tribunal=route.tribunal, grau=grau
    )
    state, command = court_sessions.request_court_login(
        session,
        escritorio_id=current.escritorio_id,
        usuario_id=current.usuario_id,
        sistema=sistema,
        tribunal=route.tribunal,
        grau=grau,
        url_login=url_login,
        processo_instancia_id=instancia.id if instancia else None,
    )
    session.commit()
    return CourtLoginOut(
        sistema=state.sistema,
        tribunal=state.tribunal,
        grau=state.grau,
        status=state.status,
        command_id=command.id,
    )


@router.get("/processos/{processo_id}/tribunal/sessao", response_model=SessaoOut)
def sessao_tribunal(
    processo_id: int,
    session: Session = Depends(get_session),
    current: CurrentUser = Depends(get_current_user),
) -> SessaoOut:
    processo = _get_owned_processo(session, processo_id, current)
    rotas: list[SessaoRotaOut] = []
    for grau in ("1", "2"):
        route = resolve_route(processo.tribunal, grau)
        sistema = processo.sistema or (route.sistema if route else None) or "PJe"
        tribunal = route.tribunal if route else (processo.tribunal or "DESCONHECIDO")
        state = court_sessions.session_state_for(
            session,
            escritorio_id=current.escritorio_id,
            sistema=sistema,
            tribunal=tribunal,
            grau=grau,
        )
        rotas.append(
            SessaoRotaOut(
                sistema=sistema,
                tribunal=tribunal,
                grau=grau,
                status=state.status if state else "desconectado",
                version_marker=state.version_marker if state else None,
                last_confirmed_at=state.last_confirmed_at if state else None,
                last_error_code=state.last_error_code if state else None,
            )
        )
    return SessaoOut(processo_id=processo.id, rotas=rotas)
