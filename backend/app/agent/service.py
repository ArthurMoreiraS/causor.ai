"""Agent workflow service.

Classifies an intimation, computes the deterministic deadline from that
classification, drafts a petition proposal, and persists both as SOR rows.
The result is always a draft. Irreversible filing is handled by the approval
gate/API, not by this service.
"""

from __future__ import annotations

from sqlalchemy import select
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


def _template_for(
    session: Session,
    *,
    processo: models.Processo | None,
    tipo_peticao: str,
) -> models.TemplatePeticao | None:
    if processo is None:
        return None
    templates = session.scalars(
        select(models.TemplatePeticao)
        .where(models.TemplatePeticao.escritorio_id == processo.escritorio_id)
        .where(models.TemplatePeticao.ativo.is_(True))
        .order_by(models.TemplatePeticao.id.desc())
    ).all()
    normalized_tipo = tipo_peticao.strip().lower()
    for template in templates:
        if template.tipo.strip().lower() == normalized_tipo:
            return template
    return None


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

    template = _template_for(
        session,
        processo=intimacao.processo,
        tipo_peticao=classificacao.peticao_sugerida,
    )
    conteudo = draft_peticao(
        intimacao_texto=intimacao.teor,
        classificacao=classificacao,
        contexto_processo=_contexto_processo(intimacao.processo),
        template_conteudo=template.conteudo if template is not None else None,
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
