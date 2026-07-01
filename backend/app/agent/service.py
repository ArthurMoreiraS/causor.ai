"""Agent workflow service.

Classifies an intimation, computes the deterministic deadline from that
classification, drafts a petition proposal, and persists both as SOR rows.
The result is always a draft. Irreversible filing is handled by the approval
gate/API, not by this service.
"""

from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.agent.classifier import ClassificacaoIntimacao, classify_intimacao
from app.agent.drafter import draft_peticao
from app.capture.registrar import registrar_prazo
from app.prazo_engine.calendar import ForensicCalendar
from app.sor import models

# Caps to keep the drafting prompt bounded. The SOR can hold long histories; we
# inject the most recent, relevant slice and flag truncation to the model.
_MAX_ANDAMENTOS = 20
_MAX_INTIMACOES = 5
_MAX_PETICOES = 5
_TRECHO_MAX_CHARS = 500


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


def _trecho(texto: str | None, limite: int = _TRECHO_MAX_CHARS) -> str:
    if not texto:
        return "(sem texto)"
    texto = " ".join(texto.split())
    return texto if len(texto) <= limite else texto[:limite].rstrip() + " […]"


def _historico_processo(
    session: Session,
    processo: models.Processo | None,
    *,
    intimacao_atual_id: int | None = None,
) -> str | None:
    """Assemble a bounded, deterministic timeline of the process from the SOR.

    Movements (DataJud), prior intimations, and prior petitions already live in
    the SOR — this pulls the most recent slice as plain text for the drafter to
    reason over. No LLM call, no external fetch (deterministic-flow philosophy).
    """
    if processo is None:
        return None

    blocos: list[str] = []

    andamentos = session.scalars(
        select(models.Andamento)
        .where(models.Andamento.processo_id == processo.id)
        .order_by(desc(models.Andamento.data), desc(models.Andamento.id))
        .limit(_MAX_ANDAMENTOS + 1)
    ).all()
    if andamentos:
        truncado = len(andamentos) > _MAX_ANDAMENTOS
        linhas = ["Movimentações (mais recentes primeiro):"]
        for a in andamentos[:_MAX_ANDAMENTOS]:
            data_txt = a.data.date().isoformat() if a.data else "s/ data"
            linhas.append(f"- {data_txt}: {a.descricao or '(sem descrição)'}")
        if truncado:
            linhas.append("- […] (movimentações mais antigas omitidas)")
        blocos.append("\n".join(linhas))

    intimacoes = session.scalars(
        select(models.Intimacao)
        .where(models.Intimacao.processo_id == processo.id)
        .order_by(desc(models.Intimacao.data_disponibilizacao), desc(models.Intimacao.id))
    ).all()
    anteriores = [i for i in intimacoes if i.id != intimacao_atual_id][:_MAX_INTIMACOES]
    if anteriores:
        linhas = ["Intimações anteriores:"]
        for i in anteriores:
            data_txt = (
                i.data_disponibilizacao.isoformat() if i.data_disponibilizacao else "s/ data"
            )
            linhas.append(f"- {data_txt} · {i.tipo_comunicacao or 'Comunicação'}: {_trecho(i.teor)}")
        blocos.append("\n".join(linhas))

    peticoes = session.scalars(
        select(models.Peticao)
        .where(models.Peticao.processo_id == processo.id)
        .order_by(desc(models.Peticao.id))
        .limit(_MAX_PETICOES)
    ).all()
    if peticoes:
        linhas = ["Petições anteriores do escritório:"]
        for p in peticoes:
            linhas.append(f"- {p.tipo or 'Petição'} ({p.status}): {_trecho(p.conteudo)}")
        blocos.append("\n".join(linhas))

    return "\n\n".join(blocos) or None


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
    resultado = draft_peticao(
        intimacao_texto=intimacao.teor,
        classificacao=classificacao,
        contexto_processo=_contexto_processo(intimacao.processo),
        historico=_historico_processo(
            session, intimacao.processo, intimacao_atual_id=intimacao.id
        ),
        prazo_fatal=prazo.data_fatal.isoformat() if prazo.data_fatal else None,
        template_conteudo=template.conteudo if template is not None else None,
    )
    peticao = models.Peticao(
        processo_id=intimacao.processo_id,
        prazo_id=prazo.id,
        escritorio_id=intimacao.escritorio_id,
        tipo=classificacao.peticao_sugerida,
        conteudo=resultado.minuta,
        dossie={
            "contexto_consolidado": resultado.contexto_consolidado,
            "analise_providencia": resultado.analise_providencia,
            "alertas": resultado.alertas,
            "confianca": resultado.confianca,
        },
        status="rascunho",
    )
    session.add(peticao)
    session.flush()
    return prazo, peticao, classificacao
