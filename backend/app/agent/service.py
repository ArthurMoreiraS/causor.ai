"""Agent workflow service.

Classifies an intimation, computes the deterministic deadline from that
classification, drafts a petition proposal, and persists both as SOR rows.
The result is always a draft. Irreversible filing is handled by the approval
gate/API, not by this service.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.agent.classifier import ClassificacaoIntimacao, classify_intimacao
from app.agent.drafter import draft_peticao
from app.capture.registrar import registrar_prazo
from app.prazo_engine.calendar import ForensicCalendar
from app.sor import models


class MissingIntimationTextError(ValueError):
    """Raised when there is no intimation body to classify/draft from."""


def _contexto_processo(processo: models.Processo | None) -> dict:
    if processo is None:
        return {}
    return {
        "numero": processo.numero,
        "classe": processo.classe,
        "tribunal": processo.tribunal,
        "orgao_julgador": processo.orgao_julgador,
    }


def draft_from_intimacao(
    session: Session,
    intimacao: models.Intimacao,
    *,
    calendar: ForensicCalendar,
) -> tuple[models.Prazo, models.Peticao, ClassificacaoIntimacao]:
    if not intimacao.teor:
        raise MissingIntimationTextError("intimacao has no text to classify")

    classificacao = classify_intimacao(intimacao.teor)
    prazo = registrar_prazo(
        session,
        intimacao,
        dias=classificacao.prazo_dias,
        calendar=calendar,
        business_days=classificacao.dias_uteis,
        descricao=classificacao.tipo,
    )
    session.flush()

    conteudo = draft_peticao(
        intimacao_texto=intimacao.teor,
        classificacao=classificacao,
        contexto_processo=_contexto_processo(intimacao.processo),
    )
    peticao = models.Peticao(
        processo_id=intimacao.processo_id,
        prazo_id=prazo.id,
        tipo=classificacao.peticao_sugerida,
        conteudo=conteudo,
        status="rascunho",
    )
    session.add(peticao)
    session.flush()
    return prazo, peticao, classificacao
