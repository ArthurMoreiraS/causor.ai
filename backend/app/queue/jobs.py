"""Persistent job state for long-running workflows.

This first implementation runs local/dev jobs in-process. The database contract
is intentionally the same shape a Redis/RQ worker will update later.
"""

from __future__ import annotations

from dataclasses import asdict, replace
from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from app.connectors.pje.connector import PjeAssistedConnector, PjeConnectorError
from app.capture.poll import poll_oab
from app.filing.package import build_pje_package
from app.filing.render import render_minuta_pdf
from app.signing.providers import get_signature_provider
from app.sor import models
from app.vault.service import VaultError, load_pje_session_payload


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


class CredencialNaoEncontradaError(JobError):
    """Raised when a filing job references an unknown signature credential."""


class CredencialInativaError(JobError):
    """Raised when a filing job references a deactivated signature credential."""


class UnsupportedFilingSystemError(JobError):
    """Raised when a real connector is requested for an unsupported court system."""


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
) -> models.JobExecucao:
    """Execute a queued captura_oab job: run poll_oab and record status + audit.

    Não captura exceções de domínio: o chamador (scheduler) faz rollback do estado
    parcial de captura e registra a falha numa transação limpa.
    """
    job = get_job(session, job_id)
    if job.tipo != "captura_oab":
        raise JobError(f"job {job_id} nao e de captura (tipo={job.tipo})")

    payload = job.payload or {}
    try:
        oab = payload["oab"]
        uf = payload["uf"]
        escritorio_id = payload["escritorio_id"]
    except KeyError as exc:
        raise JobError(f"payload de captura incompleto: falta {exc}") from exc

    mark_running(session, job)
    result = poll_oab(
        session,
        oab=oab,
        uf=uf,
        escritorio_id=escritorio_id,
        djen=djen,
        datajud=datajud,
        calendar=calendar,
        dias_default=dias_default,
        data_inicio=data_inicio,
        data_fim=data_fim,
    )
    mark_completed(
        session,
        job,
        {
            "intimacoes_novas": result.intimacoes_novas,
            "processos_enriquecidos": result.processos_enriquecidos,
            "prazos_registrados": result.prazos_registrados,
        },
    )
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


def run_fake_protocol_job(
    session: Session,
    peticao_id: int,
    credencial_id: int | None = None,
) -> models.JobExecucao:
    """Run the first filing job locally, preserving the approval gate.

    The real PJe connector will replace this fake executor. For now it proves
    the async/job state machine and audit trail without touching a court portal.
    Only the credential id travels in payload/audit — never the vault reference.
    """

    peticao = session.get(models.Peticao, peticao_id)
    if peticao is None:
        raise PeticaoNotFoundError("peticao nao encontrada")
    if peticao.status == "protocolada":
        raise AlreadyFiledError("peticao ja protocolada")
    if peticao.status != "aprovada":
        raise ApprovalRequiredError("aprovacao obrigatoria antes do protocolo")

    if credencial_id is not None:
        credencial = session.get(models.CredencialAssinatura, credencial_id)
        if credencial is None:
            raise CredencialNaoEncontradaError("credencial de assinatura nao encontrada")
        if not credencial.ativo:
            raise CredencialInativaError("credencial de assinatura desativada")

    payload: dict = {"peticao_id": peticao.id, "modo": "fake_local"}
    if credencial_id is not None:
        payload["credencial_id"] = credencial_id

    job = create_job(
        session,
        tipo="protocolo_peticao",
        entidade="peticao",
        entidade_id=peticao.id,
        payload=payload,
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
    detalhe = {"tipo": peticao.tipo, "job_id": job.id, "protocolo": protocolo_ref}
    if credencial_id is not None:
        detalhe["credencial_id"] = credencial_id
    _audit(
        session,
        acao="peticao_protocolada",
        entidade="peticao",
        entidade_id=peticao.id,
        ator=f"usuario:{peticao.aprovada_por}" if peticao.aprovada_por is not None else "system",
        detalhe=detalhe,
    )
    return job


def _validate_signature_credential(
    session: Session,
    credencial_id: int | None,
) -> None:
    if credencial_id is None:
        return
    credencial = session.get(models.CredencialAssinatura, credencial_id)
    if credencial is None:
        raise CredencialNaoEncontradaError("credencial de assinatura nao encontrada")
    if not credencial.ativo:
        raise CredencialInativaError("credencial de assinatura desativada")


def run_pje_assisted_protocol_job(
    session: Session,
    peticao_id: int,
    *,
    credencial_id: int | None = None,
    connector: PjeAssistedConnector | None = None,
) -> models.JobExecucao:
    """Prepare a PJe filing and stop before the irreversible signature/submit.

    The lawyer logs into/signs inside PJe/PJeOffice or via a future cloud
    certificate adapter. This job records the auditable checkpoint but does not
    mark the petition as filed.
    """
    peticao = session.get(models.Peticao, peticao_id)
    if peticao is None:
        raise PeticaoNotFoundError("peticao nao encontrada")
    if peticao.status == "protocolada":
        raise AlreadyFiledError("peticao ja protocolada")
    if peticao.status != "aprovada":
        raise ApprovalRequiredError("aprovacao obrigatoria antes do protocolo")
    if (peticao.processo.sistema or "").strip().lower() != "pje":
        raise UnsupportedFilingSystemError("processo nao esta marcado como PJe")

    _validate_signature_credential(session, credencial_id)
    payload: dict = {
        "peticao_id": peticao.id,
        "sistema": "PJe",
        "modo": "pje_assistido_playwright",
    }
    if credencial_id is not None:
        payload["credencial_id"] = credencial_id

    job = create_job(
        session,
        tipo="protocolo_peticao",
        entidade="peticao",
        entidade_id=peticao.id,
        payload=payload,
        ator=f"usuario:{peticao.aprovada_por}" if peticao.aprovada_por is not None else "system",
    )
    mark_running(session, job)

    try:
        session_payload = load_pje_session_payload(session, credencial_id=credencial_id)
        package = build_pje_package(peticao, credencial_id=credencial_id)
        package = replace(
            package,
            pdf_bytes=render_minuta_pdf(
                package.conteudo or "",
                meta={
                    "processo": package.numero_processo,
                    "tipo": package.tipo_peticao,
                    "tribunal": package.tribunal,
                },
            ),
            pje_base_url=session_payload.get("url_base") if session_payload else None,
            storage_state=session_payload.get("storage_state") if session_payload else None,
        )
        checkpoint = (connector or PjeAssistedConnector()).prepare_filing(package)
    except (PjeConnectorError, VaultError) as exc:
        mark_failed(session, job, str(exc))
        return job

    # Derive the human signing handoff from the credential's provider/mode.
    # The handoff carries no secret — only the message/actions the UI shows.
    credencial = (
        session.get(models.CredencialAssinatura, credencial_id)
        if credencial_id is not None
        else None
    )
    handoff = get_signature_provider(
        credencial.provedor if credencial is not None else None,
        credencial.modo if credencial is not None else "manual_handoff",
    ).handoff(package)

    evidence = dict(checkpoint.evidence)
    evidence["handoff"] = asdict(handoff)
    resultado = {
        "peticao_id": peticao.id,
        "sistema": "PJe",
        "modo": checkpoint.modo,
        # ready_to_sign is the connector's state; the handoff signals to the UI
        # that human signature is now required (signature_required).
        "checkpoint": checkpoint.checkpoint,
        "estado": "signature_required",
        "irreversible": checkpoint.irreversible,
        "evidence": evidence,
    }
    mark_completed(session, job, resultado)
    _audit(
        session,
        acao="peticao_protocolo_preparado",
        entidade="peticao",
        entidade_id=peticao.id,
        ator=f"usuario:{peticao.aprovada_por}" if peticao.aprovada_por is not None else "system",
        escritorio_id=peticao.escritorio_id,
        detalhe={
            "job_id": job.id,
            "sistema": "PJe",
            "checkpoint": checkpoint.checkpoint,
            "assinatura_provedor": handoff.provedor,
            "assinatura_modo": handoff.modo,
            "credencial_id": credencial_id,
        },
    )
    return job


def confirm_manual_protocol(
    session: Session,
    peticao_id: int,
    *,
    protocolo: str,
    comprovante_uri: str | None = None,
    credencial_id: int | None = None,
) -> models.Peticao:
    """Record the final PJe protocol after the lawyer signs/submits externally."""
    peticao = session.get(models.Peticao, peticao_id)
    if peticao is None:
        raise PeticaoNotFoundError("peticao nao encontrada")
    if peticao.status == "protocolada":
        raise AlreadyFiledError("peticao ja protocolada")
    if peticao.status != "aprovada":
        raise ApprovalRequiredError("aprovacao obrigatoria antes do protocolo")

    peticao.status = "protocolada"
    peticao.protocolada_em = _utcnow()
    detalhe = {
        "tipo": peticao.tipo,
        "protocolo": protocolo,
        "comprovante_uri": comprovante_uri,
        "origem": "pje_assistido",
    }
    # Tie the signed act to the credential used, so the audit trail records
    # which provider/mode produced the signature. No secret is stored.
    if credencial_id is not None:
        credencial = session.get(models.CredencialAssinatura, credencial_id)
        if credencial is not None:
            detalhe["provedor"] = credencial.provedor
            detalhe["modo"] = credencial.modo
    _audit(
        session,
        acao="peticao_protocolada",
        entidade="peticao",
        entidade_id=peticao.id,
        ator=f"usuario:{peticao.aprovada_por}" if peticao.aprovada_por is not None else "system",
        escritorio_id=peticao.escritorio_id,
        detalhe=detalhe,
    )
    return peticao
