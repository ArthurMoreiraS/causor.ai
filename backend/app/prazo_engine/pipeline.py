"""Durable, tenant-scoped DJEN deadline analysis and review memory."""

from __future__ import annotations

from collections.abc import Callable
from hashlib import sha256
import json
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.deadline_interpretation import DeadlineInterpretation, interpret_deadline, supported
from app.prazo_engine.djen import compute_djen_civil_deadline
from app.prazo_engine.factory import build_calendar
from app.prazo_engine.calendar import ForensicCalendar
from app.prazo_engine.legal_rules import resolve_statutory_duration, special_regime_in_official_context
from app.sor import models

KEY = "_causor_prazo"
RULE = "djen_civel_cpc219_220_224_v1"
TERMINAL = {"calculado_a_revisar", "pendente", "sem_prazo_identificado", "confirmado"}


def memory(notice: models.Intimacao) -> dict:
    value = (notice.payload or {}).get(KEY)
    return value if isinstance(value, dict) else {}


def set_memory(notice: models.Intimacao, value: dict) -> None:
    notice.payload = {**(notice.payload or {}), KEY: value}


def source_hash(notice: models.Intimacao) -> str:
    raw = {key: value for key, value in (notice.payload or {}).items() if key not in {KEY, "_causor_oabs"}}
    source = {"teor": notice.teor, "fonte": notice.fonte, "tipo": notice.tipo_comunicacao,
              "tribunal": notice.tribunal, "disponibilizacao": notice.data_disponibilizacao,
              "publicacao": notice.data_publicacao, "classe": notice.processo.classe if notice.processo else None,
              "orgao_julgador": notice.processo.orgao_julgador if notice.processo else None, "raw": raw}
    return sha256(json.dumps(source, sort_keys=True, default=str, ensure_ascii=False).encode()).hexdigest()


def enqueue_analysis(session: Session, notice: models.Intimacao, *, retry: bool = False) -> models.JobExecucao | None:
    """The capture transaction owns both the notice and its queued analysis."""
    if notice.escritorio_id is None or notice.id is None:
        raise ValueError("intimação precisa de tenant e identidade persistida")
    session.execute(select(models.Intimacao.id).where(
        models.Intimacao.id == notice.id,
        models.Intimacao.escritorio_id == notice.escritorio_id,
    ).with_for_update())
    session.refresh(notice)
    state = memory(notice).get("status")
    if state in TERMINAL or (state == "falha" and not retry):
        return None
    if session.scalar(select(models.Prazo.id).where(
        models.Prazo.escritorio_id == notice.escritorio_id,
        models.Prazo.intimacao_id == notice.id,
    ).limit(1)) is not None:
        # Legacy/human deadlines are never inferred to have been reviewed here.
        if not state:
            set_memory(notice, {"status": "pendente", "motivo": "Prazo anterior exige conferência de origem"})
        return None
    existing = session.scalars(select(models.JobExecucao).where(
        models.JobExecucao.tipo == "analise_prazo",
        models.JobExecucao.entidade == "intimacao",
        models.JobExecucao.entidade_id == notice.id,
        models.JobExecucao.status.in_(["queued", "running"]),
    )).first()
    if existing:
        return existing
    from app.queue.jobs import create_job

    job = create_job(session, tipo="analise_prazo", entidade="intimacao", entidade_id=notice.id,
                     payload={"escritorio_id": notice.escritorio_id})
    set_memory(notice, {"status": "analisando", "job_id": job.id,
                        "fonte_sha256": source_hash(notice)})
    return job


def run_analysis(
    session: Session, job: models.JobExecucao,
    *, interpreter: Callable[[str], DeadlineInterpretation] = interpret_deadline,
) -> None:
    """Call the model outside the DB transaction; a stale claim cannot publish."""
    from app.queue.jobs import mark_completed, mark_failed
    tenant = (job.payload or {}).get("escritorio_id")
    notice = session.scalar(select(models.Intimacao).where(
        models.Intimacao.id == job.entidade_id, models.Intimacao.escritorio_id == tenant,
    ))
    if notice is None or job.tipo != "analise_prazo":
        mark_failed(session, job, "Intimação ou tenant inválido")
        session.commit()
        return
    text = notice.teor or ""
    snapshot_hash = source_hash(notice)
    raw = notice.payload or {}
    context = {
        "fonte": notice.fonte, "tipo_comunicacao": notice.tipo_comunicacao or "",
        "tribunal": notice.tribunal or "", "classe": (notice.processo.classe or str(raw.get("nomeClasse") or "")) if notice.processo else str(raw.get("nomeClasse") or ""),
        "orgao": " ".join(filter(None, (str(raw.get("nomeOrgao") or ""),
                                          notice.processo.orgao_julgador if notice.processo else None))),
    }
    session.commit()  # release the read transaction during a potentially slow LLM call
    try:
        if not text.strip():
            interpretation = DeadlineInterpretation(status="incerto", regime="incerto", confianca=0,
                                                    motivo="Teor ausente; revisão manual necessária")
        elif interpreter is interpret_deadline:
            interpretation = interpreter(text, context=context)
        else:
            interpretation = interpreter(text)
    except Exception:
        interpretation = None
    job = session.scalar(select(models.JobExecucao).where(models.JobExecucao.id == job.id)
                         .execution_options(populate_existing=True).with_for_update())
    if job is None or job.status != "running":
        session.rollback()
        return
    notice = session.scalar(select(models.Intimacao).where(
        models.Intimacao.id == job.entidade_id, models.Intimacao.escritorio_id == tenant,
    ).execution_options(populate_existing=True).with_for_update())
    if (notice is None or memory(notice).get("status") != "analisando"
            or memory(notice).get("job_id") != job.id
            or source_hash(notice) != snapshot_hash):
        mark_completed(session, job, {"status": "obsoleto"})
        if notice is not None and memory(notice).get("status") == "analisando" and memory(notice).get("job_id") == job.id:
            set_memory(notice, {"status": "falha", "job_id": job.id,
                                "motivo": "Fonte alterada; repita a análise"})
        session.commit()
        return
    if interpretation is None:
        set_memory(notice, {"status": "falha", "job_id": job.id,
                            "motivo": "Análise indisponível; tente novamente"})
        mark_failed(session, job, "Análise indisponível")
        session.commit()
        return

    valid, reason = supported(interpretation, text)
    if valid and special_regime_in_official_context(context["classe"], context["orgao"]):
        valid = False
        reason = "Classe ou órgão oficial indica regime especial; revise o prazo"
    legal_rule = resolve_statutory_duration(interpretation, text) if valid and interpretation.origem_duracao == "regra_legal" else None
    duration = legal_rule.days if legal_rule is not None else interpretation.dias
    record = {
        "status": "pendente", "job_id": job.id, "regra": RULE,
        "regime": interpretation.regime, "dias": duration,
        "origem_duracao": "regra_legal" if legal_rule else (
            "judicial_expressa" if valid else interpretation.origem_duracao),
        "regra_id": legal_rule.rule_id if legal_rule else None,
        "regra_versao": legal_rule.version if legal_rule else None,
        "fonte_normativa": legal_rule.source_url if legal_rule else None,
        "comando_literal": interpretation.comando if legal_rule else None,
        "citacao_normativa_literal": interpretation.citacao_normativa if legal_rule else None,
        "unidade": interpretation.unidade, "termo": interpretation.termo,
        "evidencia": (interpretation.comando if legal_rule else
                      interpretation.evidencia if interpretation.evidencia and interpretation.evidencia in text else None),
        "fundamento": (f"CPC art. {legal_rule.article}, § {legal_rule.paragraph}; "
                       f"{legal_rule.days} dias úteis" if legal_rule else interpretation.fundamento),
        "confianca": interpretation.confianca,
        "motivo": reason, "calendario": "nacional+recesso_CPC; feriados_e_suspensoes_locais_nao_homologados",
        "fonte_sha256": snapshot_hash,
    }
    if (interpretation.status == "sem_prazo" and interpretation.evidencia
            and interpretation.evidencia in text
            and re.search(r"\b(?:sem prazo|n[aã]o h[aá] prazo|prazo inexistente)\b",
                          interpretation.evidencia, re.IGNORECASE)):
        record["status"] = "sem_prazo_identificado"
    elif valid:
        if notice.fonte != "DJEN" or notice.data_disponibilizacao is None:
            record["motivo"] = "Fonte ou data de disponibilização ausente"
        else:
            years = range(notice.data_disponibilizacao.year - 1,
                          notice.data_disponibilizacao.year + 19)
            publication_calendar = build_calendar(years)
            publication_calendar = ForensicCalendar(
                holidays=publication_calendar._holidays)  # publication is not suspended by CPC recess
            count_calendar = build_calendar(years)
            result = compute_djen_civil_deadline(
                notice.data_disponibilizacao, duration,
                publication_calendar=publication_calendar, counting_calendar=count_calendar,
                publication=notice.data_publicacao,
            )
            existing = session.scalars(select(models.Prazo).where(
                models.Prazo.escritorio_id == tenant, models.Prazo.intimacao_id == notice.id,
            ).order_by(models.Prazo.id.desc())).first()
            if existing is not None:
                record["status"] = "pendente"
                record["motivo"] = "Prazo anterior preservado; confira sua origem"
            else:
                prazo = models.Prazo(
                    escritorio_id=tenant, processo_id=notice.processo_id, intimacao_id=notice.id,
                    descricao=notice.tipo_comunicacao, data_inicio=result.publicacao,
                    dias=result.dias, dias_uteis=True, data_fatal=result.data_fatal,
                )
                session.add(prazo)
                session.flush()
                publication_from_source = notice.data_publicacao is not None
                record.update({
                    "status": "calculado_a_revisar", "prazo_id": prazo.id,
                    "disponibilizacao": result.disponibilizacao.isoformat(),
                    "publicacao": result.publicacao.isoformat(),
                    "primeiro_dia": result.primeiro_dia.isoformat(),
                    "data_fatal": result.data_fatal.isoformat(),
                    "publicacao_origem": "fonte" if publication_from_source else "derivada_DJEN",
                    "motivo": "Revise calendário e suspensões locais antes de confirmar",
                })
    set_memory(notice, record)
    session.add(models.AuditLog(escritorio_id=tenant, ator="system", acao="prazo_analisado",
                                entidade="intimacao", entidade_id=notice.id,
                                detalhe=record.copy()))
    mark_completed(session, job, {"status": record["status"], "prazo_id": record.get("prazo_id")})
    session.commit()
