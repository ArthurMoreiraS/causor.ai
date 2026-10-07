"""Persistent, idempotent legal-work analysis and drafting jobs."""
import json
from hashlib import sha256

from pydantic import ValidationError
from sqlalchemy import select

from app.agent.work_service import (_deadline_snapshot, _source_snapshot, draft_work,
                                    prepare_work_evidence, require_current_evidence, work_fingerprint)
from app.agent.llm import LLMProviderError
from app.autos.context import get_ready_context
from app.agent.evidence import original_sources
from app.queue.work_leases import LeaseHeartbeat, owned_job
from app.sor import models


def _hash(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


def _signature(work, process, bundle, source_snapshot, *, evidence=None, deadline_snapshot=None,
               questions=(), pinned=()):
    return _hash({"version": work.versao, "work": work_fingerprint(work, process),
                  "context_id": bundle.contexto_id, "context": bundle.source_fingerprint,
                  "source": source_snapshot["sha256"],
                  "evidence": _hash(evidence) if evidence is not None else None,
                  "deadline": _hash(deadline_snapshot) if evidence is not None else None,
                  "questions": list(questions), "pinned": list(pinned)})


def input_signature(session, work, action: str, *, questions=(), pinned=()):
    process = session.get(models.Processo, work.processo_id)
    if process is None or process.escritorio_id != work.escritorio_id:
        raise ValueError("O processo deste trabalho não está disponível")
    bundle = get_ready_context(session, processo=process)
    if bundle is None:
        from app.autos.context import _missing_reasons, describe_missing

        raise ValueError(describe_missing(_missing_reasons(session, process)))
    if action == "analise":
        if not work.escopo:
            raise ValueError("Declare o escopo antes da análise")
        # Cliente e polo entram na análise; vinculá-los depois invalida as
        # evidências e obriga a refazê-la. Exigir aqui evita o retrabalho.
        if not process.cliente_id or not work.polo:
            raise ValueError("Vincule o cliente ao processo e informe o polo antes de analisar as evidências")
        if pinned:
            original_sources(session, processo=process, bundle=bundle, query="", pinned=tuple(pinned), limit=0)
        evidence = None
        deadline_snapshot = None
    elif action == "minuta":
        _, evidence = require_current_evidence(session, work)
        if not evidence.get("conferida"):
            raise ValueError("Confira as evidências antes de gerar a minuta")
        if not process.cliente_id or not work.polo:
            raise ValueError("Vincule o cliente e informe o polo antes de gerar a minuta")
        if work.peticao_id:
            prior = session.get(models.Peticao, work.peticao_id)
            if prior and prior.status in {"aprovada", "protocolando", "protocolada"}:
                raise ValueError("A minuta vinculada já foi aprovada ou enviada")
        deadline_snapshot = _deadline_snapshot(session, work, process)
    else:
        raise ValueError("Operação de trabalho inválida")
    return _signature(work, process, bundle, _source_snapshot(session, work, process),
                      evidence=evidence, deadline_snapshot=deadline_snapshot,
                      questions=questions, pinned=pinned)


def enqueue_work_job(session, *, work, user_id: int, action: str, version: int,
                     request_id: str, questions=(), pinned=()):
    """Caller holds process then work row locks; retries are resolved before version checks."""
    if action not in {"analise", "minuta"}:
        raise ValueError("Operação de trabalho inválida")
    questions, pinned = tuple(questions), tuple(pinned)
    prior = session.scalars(select(models.JobExecucao).where(
        models.JobExecucao.entidade == "trabalho_juridico",
        models.JobExecucao.entidade_id == work.id,
        models.JobExecucao.tipo.in_(["analise_trabalho", "minuta_trabalho"])
    ).order_by(models.JobExecucao.id.desc()).with_for_update().execution_options(populate_existing=True)).all()
    request = {"action": action, "version": version, "questions": list(questions), "pinned": list(pinned)}
    for job in prior:
        payload = job.payload or {}
        if (payload.get("escritorio_id") == work.escritorio_id and payload.get("usuario_id") == user_id and
                request_id in [payload.get("request_id"), *payload.get("request_aliases", [])]):
            if all(payload.get(key) == value for key, value in request.items()):
                return job
            raise ValueError("A chave de solicitação já foi usada com dados diferentes")
    if work.versao != version:
        raise ValueError("O trabalho mudou. Reabra a versão atual antes de continuar")
    signature = input_signature(session, work, action, questions=questions, pinned=pinned)
    for job in prior:
        payload = job.payload or {}
        if job.status in {"queued", "running"}:
            if (job.tipo == f"{action}_trabalho" and payload.get("escritorio_id") == work.escritorio_id and
                    payload.get("usuario_id") == user_id and payload.get("signature") == signature and
                    all(payload.get(key) == value for key, value in request.items())):
                job.payload = {**payload, "request_aliases": [*payload.get("request_aliases", []), request_id]}
                return job
            raise ValueError("Já existe uma operação em andamento para este trabalho")
    job = models.JobExecucao(tipo=f"{action}_trabalho", status="queued", entidade="trabalho_juridico",
        entidade_id=work.id, payload={**request, "request_id": request_id, "signature": signature,
                                     "escritorio_id": work.escritorio_id, "usuario_id": user_id})
    session.add(job)
    session.flush()
    session.add(models.AuditLog(escritorio_id=work.escritorio_id, ator=f"usuario:{user_id}",
        acao="operacao_trabalho_solicitada", entidade="job_execucao", entidade_id=job.id,
        detalhe={"tipo": job.tipo, "trabalho_id": work.id, "versao": version}))
    return job


def public_job(job):
    payload = job.payload or {}
    return {"id": job.id, "trabalho_id": job.entidade_id, "acao": payload.get("action"),
            "versao": payload.get("version"), "request_id": payload.get("request_id"),
            "request_ids": [payload.get("request_id"), *payload.get("request_aliases", [])],
            "status": job.status, "resultado": job.resultado, "erro": job.erro,
            "created_at": job.created_at.isoformat() if job.created_at else None}


def _audit(session, job, action, detail):
    payload = job.payload or {}
    session.add(models.AuditLog(escritorio_id=payload["escritorio_id"],
        ator=f"usuario:{payload['usuario_id']}", acao=action, entidade="job_execucao",
        entidade_id=job.id, detalhe=detail))


def fail_owned(session_factory, job_id: int, token: str, message: str):
    with session_factory() as session:
        job = owned_job(session, job_id, token)
        if job is None:
            session.rollback()
            return False
        job.status, job.erro = "failed", message
        job.lease_token = None
        job.lease_expires_at = None
        _audit(session, job, "operacao_trabalho_falhou", {"tipo": job.tipo, "motivo": message})
        session.commit()
        return True


def run_work_job(session, session_factory, job_id: int, token: str):
    job = session.get(models.JobExecucao, job_id)
    if job is None or job.tipo not in {"analise_trabalho", "minuta_trabalho"}:
        return False
    payload = job.payload or {}
    work = session.get(models.TrabalhoJuridico, job.entidade_id)
    if work is None or work.escritorio_id != payload.get("escritorio_id"):
        fail_owned(session_factory, job_id, token, "O trabalho não está disponível")
        return False
    action = payload["action"]
    try:
        if work.versao != payload["version"] or input_signature(session, work, action,
                questions=payload.get("questions", ()), pinned=payload.get("pinned", ())) != payload["signature"]:
            raise ValueError("As fontes ou o trabalho mudaram antes da execução. Solicite novamente")
        if owned_job(session, job_id, token) is None:
            session.rollback()
            return False
        session.commit()

        def guard(current_session):
            current_work = current_session.get(models.TrabalhoJuridico, job.entidade_id)
            if current_work is None or input_signature(current_session, current_work, action,
                    questions=payload.get("questions", ()), pinned=payload.get("pinned", ())) != payload["signature"]:
                raise ValueError("Os dados da operação mudaram")
            if owned_job(current_session, job_id, token) is None:
                raise LostLease()

        def analysis_before_model(_session, current_work, process, bundle, source_snapshot, _evidence):
            if _signature(current_work, process, bundle, source_snapshot,
                    questions=payload["questions"], pinned=payload["pinned"]) != payload["signature"]:
                raise ValueError("Os dados da operação mudaram antes da análise")

        def draft_before_model(current_session, current_work, process, evidence, deadline_snapshot):
            bundle = get_ready_context(current_session, processo=process)
            if bundle is None or _signature(current_work, process, bundle, evidence["source_snapshot"],
                    evidence=evidence, deadline_snapshot=deadline_snapshot) != payload["signature"]:
                raise ValueError("Os dados da operação mudaram antes da redação")

        with LeaseHeartbeat(session_factory, job_id, token):
            if action == "analise":
                result = prepare_work_evidence(session, work=work, user_id=payload["usuario_id"],
                    questions=payload["questions"], pinned=tuple(payload["pinned"]),
                    before_model=analysis_before_model, before_publish=guard)
                petition = None
            else:
                result, petition = draft_work(session, work=work, user_id=payload["usuario_id"],
                    before_model=draft_before_model, before_publish=guard)
            current_job = owned_job(session, job_id, token)
            if current_job is None:
                raise LostLease()
            current_job.resultado = {"trabalho_id": result.id, "versao": result.versao,
                                     "peticao_id": petition.id if petition else None}
            current_job.erro = None
            _audit(session, current_job, "operacao_trabalho_concluida", current_job.resultado)
            _audit(session, current_job, "minuta_gerada" if petition else "evidencias_preparadas",
                   {"trabalho_id": result.id, "versao": result.versao, "peticao_id": petition.id if petition else None})
            session.flush()
            # A model response or final flush may outlive the lease. Keep the
            # original token until this last fence, then commit domain and job together.
            if owned_job(session, job_id, token) is None:
                raise LostLease()
            current_job.status = "completed"
            current_job.lease_token = None
            current_job.lease_expires_at = None
            session.commit()
            return True
    except LostLease:
        session.rollback()
        return False
    except LLMProviderError as exc:
        session.rollback()
        fail_owned(session_factory, job_id, token, f"{exc}. Tente novamente")
        return False
    except ValueError as exc:
        session.rollback()
        # Mensagens de domínio já orientam a ação; a de "dados mudaram" vem dos guardas acima.
        message = str(exc)
        if isinstance(exc, ValidationError):
            message = "A resposta do modelo veio fora do formato esperado. Tente novamente"
        elif not message or message.startswith("Os dados da operação mudaram"):
            message = "As fontes ou o trabalho mudaram. Revise e solicite novamente"
        fail_owned(session_factory, job_id, token, message)
        return False
    except Exception:
        session.rollback()
        fail_owned(session_factory, job_id, token, "Não foi possível concluir a operação. Tente novamente")
        return False


class LostLease(Exception):
    """Another worker owns this execution; its state must remain untouched."""
