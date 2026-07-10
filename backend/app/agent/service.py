"""Agent workflow service.

Classifies an intimation, computes the deterministic deadline from that
classification, drafts a petition proposal, and persists both as SOR rows.
The result is always a draft. Irreversible filing is handled by the approval
gate/API, not by this service.
"""

from __future__ import annotations

from enum import Enum

import httpx
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.agent.classifier import ClassificacaoIntimacao, classify_intimacao
from app.agent.drafter import draft_peticao
from app.capture.datajud import DatajudClient
from app.capture.normalize import enrich_processo
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


def _processo_precisa_enriquecer(session: Session, processo: models.Processo) -> bool:
    """Heuristica: enriquecemos on-demand apenas se o processo ainda nao tem
    andamentos (DataJud) nem metadados basicos. Se ja foi capturado antes, o
    historico do SOR basta — nao refazemos a cada minuta."""
    if processo.classe is None and processo.orgao_julgador is None and processo.sistema is None:
        return True
    tem_andamentos = session.scalar(
        select(func.count()).select_from(models.Andamento).where(
            models.Andamento.processo_id == processo.id
        )
    )
    return not tem_andamentos


class EnriquecimentoResultado(str, Enum):
    """Resultado de uma tentativa de enriquecimento on-demand via DataJud.

    Distinguir os casos permite ao chamador reagir corretamente: ``INDISPONIVEL``
    é transiente e acionável (vale avisar/retentar); ``NAO_ENCONTRADO`` é
    legítimo (o processo simplesmente não está no DataJud) e não merece alerta.
    """

    OK = "ok"  # processo ficou enriquecido, ou já tinha os dados
    NAO_ENCONTRADO = "nao_encontrado"  # DataJud consultado, sem hits
    INDISPONIVEL = "indisponivel"  # DataJud errou (timeout/5xx) apos os retries
    IGNORADO = "ignorado"  # datajud ausente ou sem identificadores para consultar


def _enriquecer_processo(
    session: Session,
    processo: models.Processo,
    *,
    datajud: DatajudClient | None,
    tribunal_fallback: str | None = None,
) -> EnriquecimentoResultado:
    """Enriquece um processo on-demand via DataJud se ainda faltam metadados.

    Garante orgao_julgador, classe, sistema, data_ajuizamento e movimentacoes
    (andamentos) no SOR. Usado tanto na geracao da minuta (contexto completo)
    quanto antes de protocolar (o conector PJe precisa do orgao_julgador e do
    tribunal para navegar ate a peticao no portal).
    """
    if datajud is None:
        return EnriquecimentoResultado.IGNORADO
    if not _processo_precisa_enriquecer(session, processo):
        return EnriquecimentoResultado.OK
    tribunal = processo.tribunal or tribunal_fallback
    if not tribunal:
        return EnriquecimentoResultado.IGNORADO
    numero = processo.numero or ""
    if not numero:
        return EnriquecimentoResultado.IGNORADO
    try:
        processo_dto = datajud.consultar_processo(numero, tribunal=tribunal)
    except httpx.HTTPError:
        return EnriquecimentoResultado.INDISPONIVEL
    if processo_dto is None:
        return EnriquecimentoResultado.NAO_ENCONTRADO
    enrich_processo(session, processo_dto, escritorio_id=processo.escritorio_id)
    session.flush()
    return EnriquecimentoResultado.OK


def _ensure_processo_enriched(
    session: Session,
    processo: models.Processo,
    *,
    datajud: DatajudClient | None,
    tribunal_fallback: str | None = None,
) -> bool:
    """Wrapper booleano: True se o processo ficou enriquecido (ou ja estava).

    Preserva o contrato usado antes de protocolar — o conector PJe so pode
    seguir quando o processo tem os dados; qualquer outro resultado
    (indisponivel/nao-encontrado/sem-identificadores) e False.
    """
    return (
        _enriquecer_processo(
            session, processo, datajud=datajud, tribunal_fallback=tribunal_fallback
        )
        is EnriquecimentoResultado.OK
    )


def _ensure_enriched(
    session: Session,
    intimacao: models.Intimacao,
    *,
    datajud: DatajudClient | None,
) -> EnriquecimentoResultado:
    """Enriquece o processo on-demand via DataJud antes de redigir a minuta.

    Garante o contexto completo do processo (movimentacoes/andamentos) que o
    ``_historico_processo`` precisa. So busca quando faltar; em seguida os
    andamentos ficam no SOR para proximas minutas. Devolve o resultado para o
    chamador decidir se sinaliza contexto incompleto (INDISPONIVEL) — em vez de
    engolir a falha em silencio, como antes.
    """
    processo = intimacao.processo
    if processo is None:
        return EnriquecimentoResultado.IGNORADO
    return _enriquecer_processo(
        session, processo, datajud=datajud, tribunal_fallback=intimacao.tribunal
    )


def ensure_processo_enriched(
    session: Session,
    processo: models.Processo,
    *,
    datajud: DatajudClient | None,
    tribunal_fallback: str | None = None,
) -> bool:
    """API publico: enriquece um processo on-demand via DataJud.

    Usado pelo job de protocolo para garantir orgao_julgador/tribunal antes de
    acionar o conector PJe (Playwright). Retorna True se enriquecido/ja-ok;
    False se DataJud indisponivel — nesse caso o protocolo nao deve prosseguir.
    """
    return _ensure_processo_enriched(
        session, processo, datajud=datajud, tribunal_fallback=tribunal_fallback
    )


def draft_from_intimacao(
    session: Session,
    intimacao: models.Intimacao,
    *,
    calendar: ForensicCalendar,
    datajud: DatajudClient | None = None,
) -> tuple[models.Prazo, models.Peticao, ClassificacaoIntimacao]:
    if not intimacao.teor:
        raise MissingIntimationTextError("intimacao has no text to classify")

    # Enriquecimento on-demand: garante o contexto completo do processo
    # (andamentos do DataJud) antes de redigir a minuta. So busca quando o
    # processo ainda nao foi enriquecido; apos a primeira minuta os
    # andamentos ficam no SOR. Falhas do DataJud nao bloqueiam a minuta, mas
    # quando o DataJud esta indisponivel avisamos (alerta no dossie) para o
    # advogado saber que o contexto pode estar incompleto — em vez de silencio.
    session.refresh(intimacao)
    enriquecimento = _ensure_enriched(session, intimacao, datajud=datajud)

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

    # Fonte principal do histórico: o contexto integral e citado dos autos
    # (quando ready e com fingerprint atual). DataJud/DJEN viram cronologia
    # suplementar. Sem contexto pronto, cai no histórico limitado do SOR.
    bundle = None
    if intimacao.processo is not None:
        from app.autos.context import get_ready_context

        bundle = get_ready_context(session, processo=intimacao.processo)
    if bundle is not None:
        historico = "\n\n".join(
            parte
            for parte in (
                bundle.consolidated_text,
                bundle.inventory_text,
                f"Excertos citáveis dos autos:\n{bundle.cited_excerpts}"
                if bundle.cited_excerpts
                else None,
                _historico_processo(
                    session, intimacao.processo, intimacao_atual_id=intimacao.id
                ),
            )
            if parte
        )
    else:
        historico = _historico_processo(
            session, intimacao.processo, intimacao_atual_id=intimacao.id
        )

    resultado = draft_peticao(
        intimacao_texto=intimacao.teor,
        classificacao=classificacao,
        contexto_processo=_contexto_processo(intimacao.processo),
        historico=historico,
        prazo_fatal=prazo.data_fatal.isoformat() if prazo.data_fatal else None,
        template_conteudo=template.conteudo if template is not None else None,
    )
    alertas = list(resultado.alertas)
    if enriquecimento is EnriquecimentoResultado.INDISPONIVEL:
        alertas.append(
            "Contexto do processo incompleto: o DataJud (CNJ) esteve indisponível "
            "ao gerar esta minuta, então movimentações e dados do processo podem "
            "estar faltando. Rode a captura novamente mais tarde para completar."
        )
    dossie = {
        "contexto_consolidado": resultado.contexto_consolidado,
        "analise_providencia": resultado.analise_providencia,
        "alertas": alertas,
        "confianca": resultado.confianca,
    }
    if bundle is not None:
        from app.autos.context import latest_context

        contexto_row = latest_context(session, processo=intimacao.processo)
        dossie.update(
            {
                "contexto_id": bundle.contexto_id,
                "source_fingerprint": bundle.source_fingerprint,
                "inventario": contexto_row.inventario if contexto_row else [],
                "citations": list(bundle.citations),
                "cobertura": contexto_row.cobertura if contexto_row else {},
            }
        )
    peticao = models.Peticao(
        processo_id=intimacao.processo_id,
        prazo_id=prazo.id,
        escritorio_id=intimacao.escritorio_id,
        tipo=classificacao.peticao_sugerida,
        conteudo=resultado.minuta,
        dossie=dossie,
        status="rascunho",
    )
    session.add(peticao)
    session.flush()
    return prazo, peticao, classificacao
