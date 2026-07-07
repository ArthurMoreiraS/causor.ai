"""Enrichment backfill — fill DataJud metadata for "shell" processos.

Manual capture (``/capture/oab``) runs with ``enrich=False`` to stay fast, so it
leaves processos as shells (numero/tribunal only, ``sistema is None``). This
module backfills classe/orgao/sistema/andamentos for those shells via DataJud.

It runs in two places, both off the request's critical path:
- CLI ``enrich-processos`` (cron / Task Scheduler), tenant-optional.
- A FastAPI background task scheduled right after a manual capture returns, so
  the "Sistema" filter and processo metadata populate without blocking the UI.

DataJud rate-limits bulk sequential lookups, so calls are throttled
(``delay_seconds``) and bounded (``limit``); anything left over is picked up by
the next backfill run (idempotent — only shells with ``sistema is None`` are
queried).
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.capture.court_systems import sistema_para_tribunal
from app.capture.datajud import DatajudClient
from app.capture.normalize import enrich_processo
from app.sor import models
from app.sor.db import SessionLocal

logger = logging.getLogger(__name__)

# Bound per background run so one capture never fires an unbounded DataJud loop.
# Leftover shells are enriched by the next run (idempotent by ``sistema is None``).
DEFAULT_BACKFILL_LIMIT = 200


@dataclass
class BackfillResult:
    total: int = 0
    enriquecidos: int = 0
    sem_dados: int = 0
    sem_tribunal: int = 0
    falhas: int = 0


def backfill_enrichment(
    session: Session,
    *,
    datajud,
    escritorio_id: int | None = None,
    limit: int | None = None,
    delay_seconds: float = 0.0,
    sleeper: Callable[[float], None] = time.sleep,
) -> BackfillResult:
    """Enriquece processos ainda sem metadados do DataJud (``classe is None``).

    O ``sistema`` deixou de ser o marcador de "shell" — ele agora é deduzido do
    tribunal já na captura. ``classe`` só vem do DataJud, então é o sinal certo
    de "ainda não enriquecido". Não commita (o chamador decide). Idempotente;
    falhas isoladas do DataJud (timeout/5xx/404) não interrompem o lote.
    """
    stmt = select(models.Processo).where(models.Processo.classe.is_(None))
    if escritorio_id is not None:
        stmt = stmt.where(models.Processo.escritorio_id == escritorio_id)
    if limit is not None:
        stmt = stmt.limit(limit)

    processos = session.scalars(stmt).all()
    result = BackfillResult(total=len(processos))
    consultados = 0
    for processo in processos:
        if not processo.tribunal:
            result.sem_tribunal += 1
            continue
        if consultados > 0 and delay_seconds:
            sleeper(delay_seconds)
        consultados += 1
        try:
            dto = datajud.consultar_processo(processo.numero, tribunal=processo.tribunal)
        except httpx.HTTPError:
            result.falhas += 1
            continue
        if dto is None:
            result.sem_dados += 1
            continue
        enrich_processo(session, dto, escritorio_id=processo.escritorio_id)
        result.enriquecidos += 1
    return result


def backfill_sistema(session: Session, *, escritorio_id: int | None = None) -> int:
    """Preenche ``sistema`` (deduzido do tribunal) para processos que ainda estão
    sem ele — cobre os capturados antes da inferência existir. Determinístico e
    offline (sem DataJud), rápido o bastante para rodar no próprio request da
    captura. Não commita. Retorna quantos processos foram preenchidos.
    """
    stmt = select(models.Processo).where(
        models.Processo.sistema.is_(None),
        models.Processo.tribunal.is_not(None),
    )
    if escritorio_id is not None:
        stmt = stmt.where(models.Processo.escritorio_id == escritorio_id)
    preenchidos = 0
    for processo in session.scalars(stmt):
        sistema = sistema_para_tribunal(processo.tribunal)
        if sistema is not None:
            processo.sistema = sistema
            preenchidos += 1
    return preenchidos


def run_enrichment_backfill(
    escritorio_id: int | None = None,
    *,
    session_factory: Callable[[], Session] = SessionLocal,
    datajud_factory: Callable[[], object] = DatajudClient,
    limit: int | None = DEFAULT_BACKFILL_LIMIT,
    delay_seconds: float = 0.3,
) -> BackfillResult:
    """Wrapper com sessão própria — para ser agendado como background task.

    Abre uma sessão nova (a da request já foi fechada quando o background task
    roda), enriquece os shells do tenant, commita e fecha. Como é fire-and-forget,
    qualquer erro (DataJud fora, blip de DB) é logado e engolido — não pode
    propagar/derrubar o processo do servidor; o próximo backfill retenta
    (idempotente).
    """
    session = session_factory()
    try:
        result = backfill_enrichment(
            session,
            datajud=datajud_factory(),
            escritorio_id=escritorio_id,
            limit=limit,
            delay_seconds=delay_seconds,
        )
        session.commit()
        return result
    except Exception:
        session.rollback()
        logger.exception("backfill de enriquecimento falhou (escritorio=%s)", escritorio_id)
        return BackfillResult()
    finally:
        session.close()
