"""Persistent job state for long-running workflows.

This first implementation runs local/dev jobs in-process. The database contract
is intentionally the same shape a Redis/RQ worker will update later.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.sor import models


class JobError(RuntimeError):
    """Base exception for job orchestration failures."""


class JobNotFoundError(JobError):
    """Raised when a job does not exist."""


class PeticaoNotFoundError(JobError):
    """Raised when a filing job references an unknown petition."""


class ApprovalRequiredError(JobError):
    """Raised when a filing job is requested before human approval."""


class AlreadyFiledError(JobError):
    """Raised when a petition is already filed."""


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
        detalhe={"tipo": tipo, "entidade": entidade, "entidade_id": entidade_id},
    )
    return job


def get_job(session: Session, job_id: int) -> models.JobExecucao:
    job = session.get(models.JobExecucao, job_id)
    if job is None:
        raise JobNotFoundError(f"job {job_id} nao encontrado")
    return job


def mark_running(session: Session, job: models.JobExecucao) -> None:
    job.status = "running"
    _audit(
        session,
        acao="job_iniciado",
        entidade="job_execucao",
        entidade_id=job.id,
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
        detalhe={"tipo": job.tipo, "erro": erro},
    )


def run_fake_protocol_job(session: Session, peticao_id: int) -> models.JobExecucao:
    """Run the first filing job locally, preserving the approval gate.

    The real PJe connector will replace this fake executor. For now it proves
    the async/job state machine and audit trail without touching a court portal.
    """

    peticao = session.get(models.Peticao, peticao_id)
    if peticao is None:
        raise PeticaoNotFoundError("peticao nao encontrada")
    if peticao.status == "protocolada":
        raise AlreadyFiledError("peticao ja protocolada")
    if peticao.status != "aprovada":
        raise ApprovalRequiredError("aprovacao obrigatoria antes do protocolo")

    job = create_job(
        session,
        tipo="protocolo_peticao",
        entidade="peticao",
        entidade_id=peticao.id,
        payload={"peticao_id": peticao.id, "modo": "fake_local"},
        ator=f"usuario:{peticao.aprovada_por}" if peticao.aprovada_por is not None else "system",
    )
    mark_running(session, job)

    peticao.status = "protocolada"
    peticao.protocolada_em = _utcnow()
    protocolo_ref = f"FAKE-{peticao.id}-{job.id}"
    resultado = {
        "peticao_id": peticao.id,
        "protocolo": protocolo_ref,
        "modo": "fake_local",
        "checkpoint": "Protocolo simulado localmente; substituir pelo conector PJe.",
    }
    mark_completed(session, job, resultado)
    _audit(
        session,
        acao="peticao_protocolada",
        entidade="peticao",
        entidade_id=peticao.id,
        ator=f"usuario:{peticao.aprovada_por}" if peticao.aprovada_por is not None else "system",
        detalhe={"tipo": peticao.tipo, "job_id": job.id, "protocolo": protocolo_ref},
    )
    return job
