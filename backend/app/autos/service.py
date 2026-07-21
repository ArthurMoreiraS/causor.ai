"""Orquestração resumível da captura integral dos autos.

O agente local enumera, sobe arquivos e confirma; o backend prova a
integridade: recomputa hash, valida PDF e só marca `complete` quando a
enumeração final é idêntica à inicial e todo item tem versão verificada.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256 as sha256_digest

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agent_runtime.service import enqueue_command
from app.autos.contracts import ManifestInput
from app.autos.integrity import (
    CompletenessResult,
    InvalidPdfError,
    fingerprint_manifest,
    validate_pdf,
)
from app.sor import models
from app.storage.objects import ObjectStore

CAPTURE_TRANSITIONS = {
    "queued": {"enumerating", "not_applicable", "failed"},
    "enumerating": {"downloading", "not_applicable", "incomplete", "failed"},
    "downloading": {"verifying", "incomplete", "failed"},
    "verifying": {"complete", "incomplete", "failed"},
    "complete": set(),
    "not_applicable": set(),
    "incomplete": set(),
    "failed": set(),
}


class CaptureError(RuntimeError):
    def __init__(self, code: str, detail: str | None = None):
        super().__init__(detail or code)
        self.code = code


class CaptureTransitionError(CaptureError):
    def __init__(self, current: str, new: str):
        super().__init__("invalid_transition", f"{current} -> {new}")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _transition(capture: models.CapturaAutos, new_status: str) -> None:
    if new_status not in CAPTURE_TRANSITIONS.get(capture.status, set()):
        raise CaptureTransitionError(capture.status, new_status)
    capture.status = new_status


def resolve_capture_fonte(
    session: Session, instancia: models.ProcessoInstancia
) -> str:
    """MNI quando ha credencial ativa + perfil para a rota; senao agente."""
    from app.connectors.mni.credentials import find_active_credencial
    from app.connectors.mni.profiles import resolve_mni_profile

    if resolve_mni_profile(instancia.tribunal, instancia.grau) is None:
        return "agente"
    credencial = find_active_credencial(
        session, escritorio_id=instancia.escritorio_id, tribunal=instancia.tribunal
    )
    return "mni" if credencial is not None else "agente"


def open_capture(
    session: Session,
    *,
    processo_instancia: models.ProcessoInstancia,
    usuario_id: int | None,
    fonte: str | None = None,
) -> models.CapturaAutos:
    """Abre uma nova geração de captura e publica o trabalho na fonte certa.

    ``fonte="mni"`` roda in-backend num job persistente; ``"agente"`` mantém
    o comando enfileirado para o agente local.
    """
    processo = session.get(models.Processo, processo_instancia.processo_id)
    resolved = fonte or resolve_capture_fonte(session, processo_instancia)
    latest = session.scalar(
        select(func.max(models.CapturaAutos.generation)).where(
            models.CapturaAutos.processo_instancia_id == processo_instancia.id
        )
    )
    capture = models.CapturaAutos(
        escritorio_id=processo_instancia.escritorio_id,
        processo_instancia_id=processo_instancia.id,
        generation=(latest or 0) + 1,
        status="queued",
        started_at=_now(),
        fonte=resolved,
    )
    session.add(capture)
    session.flush()

    if resolved == "mni":
        from app.queue.jobs import create_job

        create_job(
            session,
            tipo="mni_capture",
            entidade="captura_autos",
            entidade_id=capture.id,
            payload={"capture_id": capture.id, "escritorio_id": capture.escritorio_id},
            ator=f"usuario:{usuario_id}" if usuario_id else "system",
        )
    else:
        command = enqueue_command(
            session,
            escritorio_id=processo_instancia.escritorio_id,
            usuario_id=usuario_id,
            tipo="read_process",
            idempotency_key=f"capture:{processo_instancia.id}:manifest:{capture.generation}",
            payload={
                "capture_id": capture.id,
                "processo_instancia_id": processo_instancia.id,
                "sistema": processo_instancia.sistema,
                "tribunal": processo_instancia.tribunal,
                "grau": processo_instancia.grau,
                "numero_processo": processo.numero if processo else None,
                "url_base": processo_instancia.url_base,
            },
        )
        capture.agent_command_id = command.id
    session.flush()
    return capture


def record_initial_manifest(
    session: Session,
    *,
    capture: models.CapturaAutos,
    manifest: ManifestInput,
) -> models.CapturaAutos:
    """Registra a enumeração inicial: upsert de documentos lógicos + itens."""
    if capture.status == "queued":
        _transition(capture, "enumerating")
    if capture.status != "enumerating":
        raise CaptureTransitionError(capture.status, "enumerating")

    capture.initial_fingerprint = fingerprint_manifest(manifest)
    capture.cursor_complete = manifest.cursor_complete
    capture.expected_count = len(manifest.documents)
    capture.evidence = {**(capture.evidence or {}), "initial": manifest.evidence}

    for doc_input in manifest.documents:
        documento = session.scalars(
            select(models.Documento).where(
                models.Documento.processo_instancia_id == capture.processo_instancia_id,
                models.Documento.external_id == doc_input.external_id,
            )
        ).first()
        instancia = session.get(models.ProcessoInstancia, capture.processo_instancia_id)
        if documento is None:
            documento = models.Documento(
                escritorio_id=capture.escritorio_id,
                processo_id=instancia.processo_id if instancia else None,
                processo_instancia_id=capture.processo_instancia_id,
                external_id=doc_input.external_id,
                parent_external_id=doc_input.parent_external_id,
                nome=doc_input.nome,
                tipo=doc_input.tipo,
                ordem=doc_input.ordem,
                sigiloso=doc_input.sigiloso,
            )
            session.add(documento)
            session.flush()
        else:
            documento.nome = doc_input.nome
            documento.tipo = doc_input.tipo
            documento.ordem = doc_input.ordem
            documento.sigiloso = doc_input.sigiloso

        session.add(
            models.ManifestoItem(
                captura_id=capture.id,
                documento_id=documento.id,
                external_id=doc_input.external_id,
                ordem=doc_input.ordem,
                status="pending",
            )
        )

    _transition(capture, "downloading")
    session.flush()
    return capture


def _find_item(
    session: Session, capture: models.CapturaAutos, external_id: str
) -> models.ManifestoItem:
    item = session.scalars(
        select(models.ManifestoItem).where(
            models.ManifestoItem.captura_id == capture.id,
            models.ManifestoItem.external_id == external_id,
        )
    ).first()
    if item is None:
        raise CaptureError("item_not_found", f"manifesto sem item {external_id}")
    return item


def confirm_document_upload(
    session: Session,
    *,
    capture: models.CapturaAutos,
    external_id: str,
    object_key: str,
    reported_sha256: str,
    object_store: ObjectStore,
    mime_type: str = "application/pdf",
) -> models.DocumentoArquivo:
    """Verifica o upload: recomputa hash, valida PDF e cria a versão imutável."""
    if capture.status != "downloading":
        raise CaptureTransitionError(capture.status, "downloading")

    item = _find_item(session, capture, external_id)
    if item.status == "verified" and item.documento_arquivo_id is not None:
        return session.get(models.DocumentoArquivo, item.documento_arquivo_id)

    data = object_store.get_bytes(object_key)
    digest = sha256_digest(data).hexdigest()
    if digest != reported_sha256.lower():
        item.status = "failed"
        item.error_code = "hash_mismatch"
        session.flush()
        raise CaptureError("hash_mismatch", f"hash divergente para {external_id}")

    extraction_status = "pending"
    if mime_type == "application/pdf":
        try:
            validate_pdf(data, declared_mime=mime_type)
        except InvalidPdfError as exc:
            item.status = "failed"
            item.error_code = "invalid_pdf"
            session.flush()
            raise CaptureError("invalid_pdf", str(exc)) from exc
    else:
        # Não-PDF listado pelo portal é armazenado e hasheado, nunca omitido;
        # fica unsupported_mime e bloqueia o contexto até haver extrator.
        extraction_status = "unsupported_mime"

    existing = session.scalars(
        select(models.DocumentoArquivo).where(
            models.DocumentoArquivo.documento_id == item.documento_id,
            models.DocumentoArquivo.sha256 == digest,
        )
    ).first()
    if existing is not None:
        existing.atual = True
        version = existing
    else:
        version = models.DocumentoArquivo(
            documento_id=item.documento_id,
            captura_id=capture.id,
            sha256=digest,
            storage_key=object_key,
            uri=f"object://{object_key}",
            mime_type=mime_type,
            size_bytes=len(data),
            extraction_status=extraction_status,
            atual=True,
        )
        session.add(version)
        session.flush()

    # Versões anteriores do mesmo documento lógico deixam de ser atuais.
    for previous in session.scalars(
        select(models.DocumentoArquivo).where(
            models.DocumentoArquivo.documento_id == item.documento_id,
            models.DocumentoArquivo.id != version.id,
            models.DocumentoArquivo.atual.is_(True),
        )
    ):
        previous.atual = False

    item.documento_arquivo_id = version.id
    item.status = "verified"
    item.error_code = None

    # OCR/extração nunca roda no request: fica num job persistente.
    if version.extraction_status == "pending":
        from app.queue.jobs import create_job

        create_job(
            session,
            tipo="process_document",
            entidade="documento_arquivo",
            entidade_id=version.id,
            payload={"documento_arquivo_id": version.id},
            ator="agent",
        )

    capture.captured_count = session.scalar(
        select(func.count(models.ManifestoItem.id)).where(
            models.ManifestoItem.captura_id == capture.id,
            models.ManifestoItem.status == "verified",
        )
    )
    session.flush()
    return version


def finalize_capture(
    session: Session,
    *,
    capture: models.CapturaAutos,
    final_manifest: ManifestInput,
) -> models.CapturaAutos:
    """Confere a enumeração final contra a inicial e sela o resultado."""
    if capture.status == "downloading":
        _transition(capture, "verifying")
    if capture.status != "verifying":
        raise CaptureTransitionError(capture.status, "verifying")

    capture.final_fingerprint = fingerprint_manifest(final_manifest)
    capture.evidence = {**(capture.evidence or {}), "final": final_manifest.evidence}

    items = list(
        session.scalars(
            select(models.ManifestoItem).where(models.ManifestoItem.captura_id == capture.id)
        )
    )
    statuses = {item.external_id: item.status for item in items}
    initial_ids = {item.external_id for item in items}
    final_ids = {doc.external_id for doc in final_manifest.documents}

    missing = sorted(initial_ids - final_ids)
    extra = sorted(final_ids - initial_ids)
    failed = sorted(
        external_id
        for external_id in initial_ids | final_ids
        if statuses.get(external_id) != "verified"
    )
    complete = (
        capture.cursor_complete
        and final_manifest.cursor_complete
        and capture.initial_fingerprint == capture.final_fingerprint
        and not missing
        and not extra
        and not failed
    )
    result = CompletenessResult(complete=complete, missing=missing, extra=extra, failed=failed)

    capture.missing_count = len(result.missing) + len(result.extra) + len(result.failed)
    capture.completed_at = _now()
    if result.complete:
        _transition(capture, "complete")
    else:
        _transition(capture, "incomplete")
        capture.error_code = _incompleteness_code(capture, result)
    session.flush()
    return capture


def _incompleteness_code(
    capture: models.CapturaAutos, result: CompletenessResult
) -> str:
    if capture.initial_fingerprint != capture.final_fingerprint:
        return "manifest_changed"
    if result.missing or result.extra:
        return "manifest_changed"
    if result.failed:
        return "items_unverified"
    if not capture.cursor_complete:
        return "cursor_incomplete"
    return "incomplete"
