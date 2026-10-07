"""Persistent job state for long-running workflows.

This first implementation runs local/dev jobs in-process. The database contract
is intentionally the same shape a Redis/RQ worker will update later.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.capture.poll import PollResult, poll_oab
from app.sor import models


class JobError(RuntimeError):
    """Base exception for job orchestration failures."""


class JobNotFoundError(JobError):
    """Raised when a job does not exist."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _audit(
    session: Session,
    *,
    acao: str,
    entidade: str,
    entidade_id: int,
    ator: str = "system",
    escritorio_id: int | None = None,
    detalhe: dict | None = None,
) -> None:
    session.add(
        models.AuditLog(
            escritorio_id=escritorio_id,
            ator=ator,
            acao=acao,
            entidade=entidade,
            entidade_id=entidade_id,
            detalhe=detalhe or {},
        )
    )


def _job_escritorio_id(session: Session, job: models.JobExecucao) -> int | None:
    """Resolve the tenant that owns a job."""
    if job.entidade == "escritorio":
        return job.entidade_id
    if job.entidade == "oab_monitorada" and job.entidade_id is not None:
        oab = session.get(models.OabMonitorada, job.entidade_id)
        if oab is not None:
            return oab.escritorio_id
    if job.entidade == "peticao" and job.entidade_id is not None:
        peticao = session.get(models.Peticao, job.entidade_id)
        if peticao is not None:
            return peticao.escritorio_id

    escritorio_id = (job.payload or {}).get("escritorio_id")
    return escritorio_id if isinstance(escritorio_id, int) else None


def create_job(
    session: Session,
    *,
    tipo: str,
    entidade: str | None = None,
    entidade_id: int | None = None,
    payload: dict | None = None,
    ator: str = "system",
) -> models.JobExecucao:
    job = models.JobExecucao(
        tipo=tipo,
        status="queued",
        entidade=entidade,
        entidade_id=entidade_id,
        payload=payload or {},
    )
    session.add(job)
    session.flush()
    _audit(
        session,
        acao="job_criado",
        entidade="job_execucao",
        entidade_id=job.id,
        ator=ator,
        escritorio_id=_job_escritorio_id(session, job),
        detalhe={"tipo": tipo, "entidade": entidade, "entidade_id": entidade_id},
    )
    return job


def get_job(session: Session, job_id: int) -> models.JobExecucao:
    job = session.get(models.JobExecucao, job_id)
    if job is None:
        raise JobNotFoundError(f"job {job_id} nao encontrado")
    return job


def _parse_payload_date(value: object) -> date | None:
    """Lê uma data do payload JSON do job (ISO string) de forma tolerante."""
    if value is None:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def _windows(data_inicio: date, data_fim: date, batch_days: int):
    """Yield inclusive (start, end) date windows of ``batch_days`` covering the range."""
    if batch_days <= 0:
        yield (data_inicio, data_fim)
        return
    cursor = data_inicio
    while cursor <= data_fim:
        end = min(cursor + timedelta(days=batch_days - 1), data_fim)
        yield (cursor, end)
        if end >= data_fim:
            break
        cursor = end + timedelta(days=1)


def _advance_manual_oab_cursor(
    session: Session, job: models.JobExecucao, data_inicio: date | None, data_fim: date | None,
) -> None:
    """Only a complete manual or scheduled window advances a monitored OAB."""
    monitored_id = (job.payload or {}).get("oab_monitorada_id")
    if job.entidade == "oab_monitorada":
        monitored_id = job.entidade_id
    office_id = (job.payload or {}).get("escritorio_id") if job.entidade == "oab_monitorada" else job.entidade_id
    if (
        job.status != "completed" or job.entidade not in ("escritorio", "oab_monitorada")
        or not isinstance(monitored_id, int) or data_inicio is None or data_fim is None
        or data_inicio > data_fim or data_fim > datetime.now(ZoneInfo("America/Sao_Paulo")).date()
    ):
        return
    session.flush()
    monitored = session.scalar(select(models.OabMonitorada).where(
        models.OabMonitorada.id == monitored_id).execution_options(populate_existing=True).with_for_update())
    if monitored is None or not monitored.ativo or monitored.escritorio_id != office_id:
        return
    if monitored.cursor_data is None or data_fim > monitored.cursor_data:
        monitored.cursor_data = data_fim
    monitored.ultima_captura_em = datetime.now(timezone.utc)


def run_capture_oab_job(
    session: Session,
    job_id: int,
    *,
    djen,
    datajud,
    calendar,
    data_inicio: date | None = None,
    data_fim: date | None = None,
    dias_default: int = 15,
    enrich: bool = True,
    batch_days: int | None = None,
    commit_each: Callable[[Session], None] | None = None,
    hoje: date | None = None,
) -> models.JobExecucao:
    """Execute a queued captura_oab job: run poll_oab and record status + audit.

    Não captura exceções de domínio: o chamador (scheduler/worker) faz rollback do
    estado parcial de captura e registra a falha numa transação limpa.

    Quando ``batch_days`` > 0 e ambas as datas limites são informadas, o intervalo
    é quebrado em janelas de ``batch_days`` dias; cada janela roda como uma chamada
    separada do poll_oab e, se ``commit_each`` for informado, a transação é
    commitada entre janelas. Isso evita transações longas/locks estendidos e
    permite que o frontend acompanhe o progresso lendo ``job.resultado`` (campos
    ``windows_done``/``windows_total``). Sem ``batch_days`` (default) mantém o
    comportamento de uma única transação, compatível com o scheduler legado.
    """
    job = _lock_capture_job(session, job_id)
    if job.tipo != "captura_oab":
        raise JobError(f"job {job_id} nao e de captura (tipo={job.tipo})")

    payload = job.payload or {}
    try:
        oab = payload["oab"]
        uf = payload["uf"]
        escritorio_id = payload["escritorio_id"]
    except KeyError as exc:
        raise JobError(f"payload de captura incompleto: falta {exc}") from exc

    # A janela vive no payload do job. Antes ela vinha só dos argumentos da
    # função: quem executasse o job sem repassá-los transformava uma captura de
    # 3 dias numa varredura do histórico inteiro da OAB. O argumento explícito
    # ainda ganha (o scheduler recalcula pelo cursor); o payload é o fallback.
    if data_inicio is None:
        data_inicio = _parse_payload_date(payload.get("data_inicio"))
    if data_fim is None:
        data_fim = _parse_payload_date(payload.get("data_fim"))

    mark_running(session, job)
    session.flush()

    windowed = bool(batch_days and batch_days > 0 and data_inicio is not None and data_fim is not None)
    if not windowed:
        result = poll_oab(
            session,
            oab=oab,
            uf=uf,
            escritorio_id=escritorio_id,
            djen=djen,
            datajud=datajud,
            calendar=calendar,
            dias_default=dias_default,
            enrich=enrich,
            hoje=hoje,
            data_inicio=data_inicio,
            data_fim=data_fim,
        )
        outcome = {
                "intimacoes_novas": result.intimacoes_novas,
                "publicacoes_encontradas": result.publicacoes_encontradas,
                "processos_enriquecidos": result.processos_enriquecidos,
                "prazos_registrados": result.prazos_registrados,
                "prazos_historicos": result.prazos_historicos,
                "djen_indisponivel": result.djen_indisponivel,
                "djen_erro": result.djen_erro,
            }
        if result.djen_indisponivel:
            job.resultado = outcome
            mark_failed(session, job, result.djen_erro or "DJEN indisponível")
        else:
            outcome.update(_sugestao_uf(djen, oab=oab, uf=uf, data_inicio=data_inicio,
                                        data_fim=data_fim, publicacoes=result.publicacoes_encontradas))
            mark_completed(session, job, outcome)
        _advance_manual_oab_cursor(session, job, data_inicio, data_fim)
        return job

    windows = list(_windows(data_inicio, data_fim, batch_days))  # type: ignore[arg-type]
    total_windows = len(windows)
    totals = PollResult()
    djen_indisponivel = False
    djen_erro: str | None = None
    for i, (w_start, w_end) in enumerate(windows, 1):
        job = _lock_capture_job(session, job_id)
        partial = poll_oab(
            session,
            oab=oab,
            uf=uf,
            escritorio_id=escritorio_id,
            djen=djen,
            datajud=datajud,
            calendar=calendar,
            dias_default=dias_default,
            enrich=enrich,
            hoje=hoje,
            data_inicio=w_start,
            data_fim=w_end,
        )
        totals = PollResult(
            intimacoes_novas=totals.intimacoes_novas + partial.intimacoes_novas,
            publicacoes_encontradas=totals.publicacoes_encontradas + partial.publicacoes_encontradas,
            processos_enriquecidos=totals.processos_enriquecidos + partial.processos_enriquecidos,
            prazos_registrados=totals.prazos_registrados + partial.prazos_registrados,
            prazos_historicos=totals.prazos_historicos + partial.prazos_historicos,
            djen_indisponivel=totals.djen_indisponivel or partial.djen_indisponivel,
            djen_erro=partial.djen_erro or totals.djen_erro,
        )
        if partial.djen_indisponivel:
            djen_indisponivel = True
            djen_erro = partial.djen_erro
        job.resultado = {
            "intimacoes_novas": totals.intimacoes_novas,
            "publicacoes_encontradas": totals.publicacoes_encontradas,
            "processos_enriquecidos": totals.processos_enriquecidos,
            "prazos_registrados": totals.prazos_registrados,
            "prazos_historicos": totals.prazos_historicos,
            "windows_done": i,
            "windows_total": total_windows,
            "window_atual": {
                "data_inicio": w_start.isoformat(),
                "data_fim": w_end.isoformat(),
            },
            "djen_indisponivel": djen_indisponivel,
            "djen_erro": djen_erro,
        }
        if partial.djen_indisponivel:
            mark_failed(session, job, djen_erro or "DJEN indisponível")
            session.flush()
            if commit_each is not None:
                commit_each(session)
            return job
        session.flush()
        if commit_each is not None:
            commit_each(session)
            job = get_job(session, job_id)

    job = _lock_capture_job(session, job_id)
    mark_completed(
        session,
        job,
        {
            "intimacoes_novas": totals.intimacoes_novas,
            "publicacoes_encontradas": totals.publicacoes_encontradas,
            "processos_enriquecidos": totals.processos_enriquecidos,
            "prazos_registrados": totals.prazos_registrados,
            "prazos_historicos": totals.prazos_historicos,
            "windows_done": total_windows,
            "windows_total": total_windows,
            "djen_indisponivel": djen_indisponivel,
            "djen_erro": djen_erro,
            **_sugestao_uf(djen, oab=oab, uf=uf, data_inicio=data_inicio, data_fim=data_fim,
                           publicacoes=totals.publicacoes_encontradas),
        },
    )
    _advance_manual_oab_cursor(session, job, data_inicio, data_fim)
    return job


def _sugestao_uf(djen, *, oab: str, uf: str, data_inicio: date | None, data_fim: date | None,
                 publicacoes: int) -> dict:
    """Quando o DJEN não devolve nada para OAB/UF, sugere as UFs da inscrição.

    Melhor esforço: falha na consulta extra não altera o resultado da captura.
    """
    if publicacoes or data_inicio is None or data_fim is None or not hasattr(djen, "ufs_da_inscricao"):
        return {}
    try:
        ufs = djen.ufs_da_inscricao(oab, data_inicio=data_inicio, data_fim=data_fim)
    except httpx.HTTPError:
        return {}
    return {"ufs_sugeridas": [item for item in ufs if item != uf.upper()][:5]}


def _lock_capture_job(session: Session, job_id: int) -> models.JobExecucao:
    job = session.scalar(select(models.JobExecucao).where(models.JobExecucao.id == job_id)
                         .execution_options(populate_existing=True).with_for_update())
    if job is None or (job.payload or {}).get("removida"):
        raise JobError("Captura cancelada pela remoção da OAB")
    if (job.payload or {}).get("agendada") is True:
        if job.status not in ("queued", "running"):
            raise JobError("Captura agendada já encerrada")
        monitored = session.scalar(select(models.OabMonitorada).where(
            models.OabMonitorada.id == job.entidade_id,
            models.OabMonitorada.escritorio_id == job.payload.get("escritorio_id"),
        ).execution_options(populate_existing=True))
        if (job.entidade != "oab_monitorada" or monitored is None or not monitored.ativo
                or monitored.oab != job.payload.get("oab") or monitored.uf != job.payload.get("uf")):
            raise JobError("Captura agendada cancelada: OAB ausente ou inativa")
    return job


def mark_running(session: Session, job: models.JobExecucao) -> None:
    job.status = "running"
    _audit(
        session,
        acao="job_iniciado",
        entidade="job_execucao",
        entidade_id=job.id,
        escritorio_id=_job_escritorio_id(session, job),
        detalhe={"tipo": job.tipo},
    )


def mark_completed(session: Session, job: models.JobExecucao, resultado: dict | None = None) -> None:
    job.status = "completed"
    job.resultado = resultado or {}
    job.erro = None
    _audit(
        session,
        acao="job_concluido",
        entidade="job_execucao",
        entidade_id=job.id,
        escritorio_id=_job_escritorio_id(session, job),
        detalhe={"tipo": job.tipo, "resultado": job.resultado},
    )


def mark_failed(session: Session, job: models.JobExecucao, erro: str) -> None:
    job.status = "failed"
    job.erro = erro
    _audit(
        session,
        acao="job_falhou",
        entidade="job_execucao",
        entidade_id=job.id,
        escritorio_id=_job_escritorio_id(session, job),
        detalhe={"tipo": job.tipo, "erro": erro},
    )


def fail_stale_running_jobs(
    session: Session,
    *,
    older_than_minutes: int,
    now: datetime | None = None,
) -> list[models.JobExecucao]:
    """Fail stale capture/analysis jobs only. Never infer the outcome of a filing.

    Document jobs have a separate recovery path that honors their row locks.
    """
    if older_than_minutes <= 0:
        raise ValueError("older_than_minutes must be positive")
    now = now or _utcnow()
    cutoff = now - timedelta(minutes=older_than_minutes)
    stmt = select(models.JobExecucao).where(
        models.JobExecucao.status == "running",
        models.JobExecucao.tipo.in_(["captura_oab", "analise_prazo"]),
        models.JobExecucao.updated_at <= cutoff,
    ).with_for_update(skip_locked=True)
    stale: list[models.JobExecucao] = []
    for job in session.scalars(stmt):
        updated_at = job.updated_at
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)
        if updated_at <= cutoff:
            mark_failed(
                session,
                job,
                f"job interrompido: permaneceu running por mais de {older_than_minutes} minutos",
            )
            if job.tipo == "analise_prazo" and job.entidade_id is not None:
                from app.prazo_engine.pipeline import memory, set_memory

                notice = session.scalar(select(models.Intimacao).where(
                    models.Intimacao.id == job.entidade_id).with_for_update())
                if (notice and notice.escritorio_id == _job_escritorio_id(session, job)
                        and memory(notice).get("status") == "analisando"
                        and memory(notice).get("job_id") == job.id):
                    set_memory(notice, {"status": "falha", "job_id": job.id,
                                        "motivo": "Análise interrompida; tente novamente"})
            stale.append(job)
    return stale
