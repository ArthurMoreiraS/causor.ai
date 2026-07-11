"""Persistent job state for long-running workflows.

This first implementation runs local/dev jobs in-process. The database contract
is intentionally the same shape a Redis/RQ worker will update later.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, replace
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.connectors.pje.connector import PjeConnectorError
from app.connectors.drivers import (
    UnsupportedFilingSystemError as FilingDriverUnsupported,
)
from app.connectors.drivers import get_filing_driver
from app.agent.service import ensure_processo_enriched
from app.capture.court_routing import resolve_route
from app.capture.datajud import DatajudClient
from app.capture.poll import PollResult, poll_oab
from app.filing.package import build_pje_package
from app.filing.render import render_minuta_pdf
from app.filing.timbrado import load_timbrado
from app.settings import settings
from app.signing.providers import get_signature_provider
from app.connectors.sessions import session_state_for
from app.sor import models
from app.vault.service import VaultError


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


class ProcessoSemOrgaoError(JobError):
    """Raised when a filing job cannot proceed: orgao_julgador/tribunal missing.

    The PJe assisted connector needs the court unit (orgao_julgador) and the
    tribunal to navigate to the right petition page. We try to enrich the
    processo on-demand via DataJud before filing; if that fails (DataJud
    unavailable) we abort rather than file into the wrong/unknown court.
    """


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
    batch_days: int | None = None,
    commit_each: Callable[[Session], None] | None = None,
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
                "djen_indisponivel": result.djen_indisponivel,
                "djen_erro": result.djen_erro,
            },
        )
        return job

    windows = list(_windows(data_inicio, data_fim, batch_days))  # type: ignore[arg-type]
    total_windows = len(windows)
    totals = PollResult()
    djen_indisponivel = False
    djen_erro: str | None = None
    for i, (w_start, w_end) in enumerate(windows, 1):
        partial = poll_oab(
            session,
            oab=oab,
            uf=uf,
            escritorio_id=escritorio_id,
            djen=djen,
            datajud=datajud,
            calendar=calendar,
            dias_default=dias_default,
            data_inicio=w_start,
            data_fim=w_end,
        )
        totals = PollResult(
            intimacoes_novas=totals.intimacoes_novas + partial.intimacoes_novas,
            processos_enriquecidos=totals.processos_enriquecidos + partial.processos_enriquecidos,
            prazos_registrados=totals.prazos_registrados + partial.prazos_registrados,
            djen_indisponivel=totals.djen_indisponivel or partial.djen_indisponivel,
            djen_erro=partial.djen_erro or totals.djen_erro,
        )
        if partial.djen_indisponivel:
            djen_indisponivel = True
            djen_erro = partial.djen_erro
        job.resultado = {
            "intimacoes_novas": totals.intimacoes_novas,
            "processos_enriquecidos": totals.processos_enriquecidos,
            "prazos_registrados": totals.prazos_registrados,
            "windows_done": i,
            "windows_total": total_windows,
            "window_atual": {
                "data_inicio": w_start.isoformat(),
                "data_fim": w_end.isoformat(),
            },
            "djen_indisponivel": djen_indisponivel,
            "djen_erro": djen_erro,
        }
        session.flush()
        if commit_each is not None:
            commit_each(session)
            job = get_job(session, job_id)

    mark_completed(
        session,
        job,
        {
            "intimacoes_novas": totals.intimacoes_novas,
            "processos_enriquecidos": totals.processos_enriquecidos,
            "prazos_registrados": totals.prazos_registrados,
            "windows_done": total_windows,
            "windows_total": total_windows,
            "djen_indisponivel": djen_indisponivel,
            "djen_erro": djen_erro,
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
    """Fail jobs left running after a worker/process interruption."""
    now = now or _utcnow()
    cutoff = now - timedelta(minutes=older_than_minutes)
    stmt = select(models.JobExecucao).where(models.JobExecucao.status == "running")
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
            stale.append(job)
    return stale


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


def run_pje_protocol_job(
    session: Session,
    peticao_id: int,
    *,
    credencial_id: int | None = None,
    usuario_id: int | None = None,
    connector: object | None = None,
    datajud: DatajudClient | None = None,
    submit: bool = True,
    filing_mode: str | None = None,
) -> models.JobExecucao:
    """Protocola uma peticao roteando pelo sistema do tribunal (PJe/e-SAJ/...).

    Resolve ``processo -> (tribunal, grau) -> sistema`` e despacha o driver do
    sistema (``get_filing_driver``). A sessao autenticada vive no agente local;
    ``submit=True`` exige ``CourtSessionState`` "conectado" para a rota — sem
    isso o job falha com mensagem clara ("conecte o tribunal"). ``credencial_id``
    referencia apenas assinatura em nuvem (handoff), nunca sessao.
    ``filing_mode`` sobrepoe ``settings.filing_mode`` (sandbox na demo).

    ``submit=True`` (default) clica em Assinar/Protocolar no PJe, aguarda o
    comprovante, captura o numero do protocolo e marca a peticao como
    ``protocolada`` automaticamente — o ato irreversivel acontece no PJe, nao no
    Causor; o Causor so orquestra o clique e captura o comprovante. O
    certificado/PIN fica no PJeOffice local do advogado (nao no Causor).

    ``submit=False`` (modo preparo) para em ``ready_to_sign`` e devolve o
    handoff pro advogado assinar fora e registrar o numero por
    ``confirm_manual_protocol`` — fallback para provedores sem automacao.

    Antes de acionar o conector, enriquece o processo on-demand via DataJud
    quando faltar orgao_julgador/tribunal. ``tribunal`` e obrigatorio
    (hard-stop); ``orgao_julgador`` e melhor-esforco.
    """
    peticao = session.get(models.Peticao, peticao_id)
    if peticao is None:
        raise PeticaoNotFoundError("peticao nao encontrada")
    if peticao.status == "protocolada":
        raise AlreadyFiledError("peticao ja protocolada")
    if peticao.status != "aprovada":
        raise ApprovalRequiredError("aprovacao obrigatoria antes do protocolo")

    processo = peticao.processo

    # Gate fail-closed: protocolo exige contexto ready/atual (ou override do
    # advogado) e que a minuta tenha sido redigida sobre o mesmo estado dos
    # autos (fingerprint da peticao == fingerprint atual do contexto).
    from app.autos.context import (
        ContextNotReadyError,
        current_fingerprint,
        require_ready_context,
    )

    gate = require_ready_context(
        session, processo=processo, usuario_id=usuario_id, action="file"
    )
    if gate == "ready":
        dossie = peticao.dossie if isinstance(peticao.dossie, dict) else {}
        stored_fingerprint = dossie.get("source_fingerprint")
        if stored_fingerprint != current_fingerprint(session, processo=processo):
            raise ContextNotReadyError(
                processo_id=processo.id, missing=["peticao:fingerprint_divergente"]
            )

    if not processo.tribunal:
        raise ProcessoSemOrgaoError(
            "processo sem tribunal: nao e possivel protocolar sem saber o tribunal."
        )
    if not processo.orgao_julgador and datajud is not None:
        ensure_processo_enriched(session, processo, datajud=datajud)

    # Roteamento: processo -> (tribunal, grau) -> sistema -> driver.
    grau = (getattr(processo, "grau", None) or "1")
    route = resolve_route(processo.tribunal, grau)
    sistema = processo.sistema or (route.sistema if route is not None else None) or "PJe"
    mode = filing_mode or settings.filing_mode
    try:
        driver = connector or get_filing_driver(sistema, mode=mode)
    except FilingDriverUnsupported as exc:
        raise UnsupportedFilingSystemError(str(exc)) from exc

    _validate_signature_credential(session, credencial_id)
    payload: dict = {
        "peticao_id": peticao.id,
        "sistema": sistema,
        "modo": "pje_playwright_submit" if submit else "pje_assistido_playwright",
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
    if submit:
        peticao.status = "protocolando"
        session.flush()

    try:
        # A sessão autenticada vive no agente local; aqui só o estado derivado.
        # Fail-closed no ato irreversível: submit exige rota "conectado". O
        # preparo/handoff manual (submit=False) não abre o tribunal.
        if submit:
            estado = session_state_for(
                session,
                escritorio_id=peticao.escritorio_id,
                sistema=sistema,
                tribunal=(processo.tribunal or "").strip().upper(),
                grau=grau,
            )
            if estado is None or estado.status != "conectado":
                raise PjeConnectorError(
                    f"conecte o tribunal {processo.tribunal} ({sistema} - {grau}o grau) "
                    "pelo Causor antes de protocolar"
                )

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
                timbrado=load_timbrado(session, peticao.escritorio_id),
            ),
            pje_base_url=route.url_login if route is not None else None,
        )
        checkpoint = driver.prepare_filing(package, submit=submit)
    except (PjeConnectorError, VaultError) as exc:
        mark_failed(session, job, str(exc))
        if submit:
            peticao.status = "aprovada"  # reverte: continua aprovada, nao protocolada
            session.flush()
        return job

    if checkpoint.checkpoint == "protocolado":
        protocolo = checkpoint.evidence.get("protocolo")
        peticao.status = "protocolada"
        peticao.protocolada_em = _utcnow()
        session.flush()
        resultado = {
            "peticao_id": peticao.id,
            "sistema": sistema,
            "modo": checkpoint.modo,
            "checkpoint": "protocolado",
            "estado": "protocolada",
            "irreversible": True,
            "protocolo": protocolo,
            "evidence": checkpoint.evidence,
        }
        mark_completed(session, job, resultado)
        _audit(
            session,
            acao="peticao_protocolada",
            entidade="peticao",
            entidade_id=peticao.id,
            ator=f"usuario:{peticao.aprovada_por}" if peticao.aprovada_por is not None else "system",
            escritorio_id=peticao.escritorio_id,
            detalhe={
                "job_id": job.id,
                "sistema": sistema,
                "protocolo": protocolo,
                "origem": checkpoint.modo,
                "credencial_id": credencial_id,
            },
        )
        return job

    # ready_to_sign: handoff manual (fallback).
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
        "checkpoint": "ready_to_sign",
        "estado": "signature_required",
        "irreversible": False,
        "evidence": evidence,
    }
    # No modo submit, ready_to_sign significa que o conectorNao conseguiu
    # concluir o envio (ex.: assinatura_pendente_pjeoffice). A peticao volta
    # para aprovada — o advogado confirma a assinatura manual e registra.
    if submit:
        peticao.status = "aprovada"
        session.flush()
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
            "sistema": sistema,
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
