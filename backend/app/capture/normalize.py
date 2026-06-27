"""Normalize captured DTOs into SOR rows (idempotent upserts).

- ``normalize_intimacao``: ComunicacaoDTO (DJEN) -> Intimacao, deduped by
  (fonte, fonte_id), linked to an existing Processo when the CNJ number matches.
- ``enrich_processo``: ProcessoDTO (DataJud) -> Processo (+ Andamentos),
  upserted by (escritorio_id, canonical numero); movements deduped.

Process numbers are stored in canonical digit-only form so DJEN (masked) and
DataJud (unmasked) sources reconcile to the same Processo.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.capture.datajud import ProcessoDTO
from app.capture.djen import ComunicacaoDTO
from app.sor import models

_NON_DIGIT = re.compile(r"\D")


def canonical_numero(numero: str | None) -> str | None:
    if not numero:
        return None
    return _NON_DIGIT.sub("", numero)


def normalize_intimacao(
    session: Session, dto: ComunicacaoDTO, *, escritorio_id: int
) -> models.Intimacao:
    existing = session.scalar(
        select(models.Intimacao).where(
            models.Intimacao.fonte == "DJEN", models.Intimacao.fonte_id == dto.id
        )
    )
    if existing is not None:
        if existing.processo_id is None and existing.numero_processo:
            processo = _get_or_create_processo(
                session,
                numero=existing.numero_processo,
                escritorio_id=escritorio_id,
                tribunal=existing.tribunal or dto.tribunal,
            )
            existing.processo_id = processo.id
        return existing

    numero = canonical_numero(dto.numero_processo)
    processo = (
        _get_or_create_processo(
            session,
            numero=numero,
            escritorio_id=escritorio_id,
            tribunal=dto.tribunal,
        )
        if numero
        else None
    )

    intimacao = models.Intimacao(
        processo_id=processo.id if processo else None,
        escritorio_id=escritorio_id,
        fonte="DJEN",
        fonte_id=dto.id,
        numero_processo=numero,
        tribunal=dto.tribunal,
        tipo_comunicacao=dto.tipo_comunicacao,
        teor=dto.texto,
        data_disponibilizacao=dto.data_disponibilizacao,
        payload=dto.raw or None,
    )
    session.add(intimacao)
    return intimacao


def _get_or_create_processo(
    session: Session,
    *,
    numero: str,
    escritorio_id: int,
    tribunal: str | None = None,
) -> models.Processo:
    processo = session.scalar(
        select(models.Processo).where(
            models.Processo.escritorio_id == escritorio_id,
            models.Processo.numero == numero,
        )
    )
    if processo is None:
        processo = models.Processo(
            escritorio_id=escritorio_id,
            numero=numero,
            tribunal=tribunal,
        )
        session.add(processo)
        session.flush()
    elif tribunal and processo.tribunal is None:
        processo.tribunal = tribunal
    return processo


def enrich_processo(session: Session, dto: ProcessoDTO, *, escritorio_id: int) -> models.Processo:
    numero = canonical_numero(dto.numero_processo)
    processo = session.scalar(
        select(models.Processo).where(
            models.Processo.escritorio_id == escritorio_id,
            models.Processo.numero == numero,
        )
    )
    if processo is None:
        processo = models.Processo(escritorio_id=escritorio_id, numero=numero)
        session.add(processo)
        session.flush()  # assign id for andamentos FK

    # Refresh metadata from the latest capture.
    processo.classe = dto.classe or processo.classe
    processo.tribunal = dto.tribunal or processo.tribunal
    processo.orgao_julgador = dto.orgao_julgador or processo.orgao_julgador
    processo.sistema = dto.sistema or processo.sistema
    processo.data_ajuizamento = dto.data_ajuizamento or processo.data_ajuizamento

    _sync_andamentos(session, processo, dto)
    return processo


def _utc_naive(value: datetime | None) -> datetime | None:
    """Normalize a datetime to naive UTC so keys compare equal across backends.

    SQLite (tests) drops tzinfo on round-trip while Postgres preserves it; this
    keeps movement dedup stable regardless of backend.
    """
    if value is None:
        return None
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _sync_andamentos(session: Session, processo: models.Processo, dto: ProcessoDTO) -> None:
    existing = session.scalars(
        select(models.Andamento).where(models.Andamento.processo_id == processo.id)
    ).all()
    seen = {(a.codigo, _utc_naive(a.data)) for a in existing}

    for mov in dto.movimentos:
        key = (mov.codigo, _utc_naive(mov.data_hora))
        if key in seen:
            continue
        seen.add(key)
        session.add(
            models.Andamento(
                processo_id=processo.id,
                codigo=mov.codigo,
                descricao=mov.nome,
                data=mov.data_hora,
            )
        )
