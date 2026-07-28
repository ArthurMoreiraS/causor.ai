"""Executor in-backend da captura MNI.

Dirige as mesmas funções de integridade do Plano 2 usando o driver MNI;
nenhuma etapa relaxa a prova de completude. Erro canônico marca a captura
``failed`` e sobe — o job nunca fica ``running``.
"""

from __future__ import annotations

from hashlib import sha256

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.autos import service as autos_service
from app.autos.contracts import ManifestDocumentInput, ManifestInput
from app.connectors.contracts import CourtManifestSnapshot, CourtTarget
from app.connectors.errors import ConnectorError, DocumentDownloadFailed, InstanceNotFound
from app.connectors.mni.client import MniClient
from app.connectors.mni.credentials import find_active_credencial, load_credencial_senha
from app.connectors.mni.profiles import resolve_mni_profile
from app.connectors.mni.reader import MniReaderDriver
from app.sor import models
from app.storage.objects import ObjectStore, get_object_store

_ACTIVE_STATUSES = {"queued", "enumerating", "downloading", "verifying"}


class MniCaptureError(RuntimeError):
    def __init__(self, code: str, detail: str | None = None):
        super().__init__(detail or code)
        self.code = code


def _target_for(session: Session, capture: models.CapturaAutos) -> CourtTarget:
    instancia = session.get(models.ProcessoInstancia, capture.processo_instancia_id)
    processo = session.get(models.Processo, instancia.processo_id)
    return CourtTarget(
        processo_instancia_id=instancia.id,
        processo_id=processo.id,
        numero_processo=processo.numero,
        sistema=instancia.sistema,
        tribunal=instancia.tribunal,
        grau=instancia.grau,
        url_base=instancia.url_base or "",
    )


def _manifest_input(snapshot: CourtManifestSnapshot) -> ManifestInput:
    return ManifestInput(
        cursor_complete=snapshot.cursor_complete,
        documents=[
            ManifestDocumentInput(
                external_id=ref.external_id,
                nome=ref.nome,
                tipo=ref.tipo,
                ordem=ref.ordem,
                parent_external_id=ref.parent_external_id,
                data_documento=ref.data_documento,
                sigiloso=ref.sigiloso,
                mime_type=ref.mime_type,
                size_hint=ref.size_hint,
                download_ref=ref.download_ref,
            )
            for ref in snapshot.documentos
        ],
        evidence=snapshot.evidence,
    )


def build_driver(session: Session, capture: models.CapturaAutos) -> MniReaderDriver:
    instancia = session.get(models.ProcessoInstancia, capture.processo_instancia_id)
    profile = resolve_mni_profile(instancia.tribunal, instancia.grau)
    credencial = find_active_credencial(
        session, escritorio_id=capture.escritorio_id, tribunal=instancia.tribunal
    )
    if profile is None or credencial is None:
        raise MniCaptureError("mni_route_unavailable")
    client = MniClient(
        url_endpoint=profile.url_endpoint,
        id_consultante=credencial.id_consultante,
        senha=load_credencial_senha(session, credencial),
    )
    return MniReaderDriver(client)


def run_mni_capture_job(
    session: Session,
    *,
    capture_id: int,
    object_store: ObjectStore | None = None,
    driver: MniReaderDriver | None = None,
) -> models.CapturaAutos:
    capture = session.get(models.CapturaAutos, capture_id)
    if capture is None:
        raise MniCaptureError("capture_not_found", str(capture_id))
    if capture.fonte != "mni":
        raise MniCaptureError("wrong_source", capture.fonte)

    store = object_store or get_object_store()
    drv = driver or build_driver(session, capture)
    target = _target_for(session, capture)
    try:
        snapshot = drv.enumerate_documents(target)
        autos_service.record_initial_manifest(
            session, capture=capture, manifest=_manifest_input(snapshot)
        )
        items = {
            item.external_id: item
            for item in session.scalars(
                select(models.ManifestoItem).where(
                    models.ManifestoItem.captura_id == capture.id
                )
            )
        }
        drv.prefetch(target, snapshot.documentos)
        for ref in snapshot.documentos:
            item = items[ref.external_id]
            try:
                data = drv.download_document(target, ref)
            except DocumentDownloadFailed as exc:
                item.status = "failed"
                item.error_code = exc.code
                session.flush()
                continue
            digest = sha256(data).hexdigest()
            key = (
                f"tenant/{capture.escritorio_id}/process/{target.processo_id}"
                f"/instance/{target.processo_instancia_id}"
                f"/document/{item.documento_id}/{digest}.bin"
            )
            store.put_bytes(key, data, ref.mime_type or "application/pdf")
            try:
                autos_service.confirm_document_upload(
                    session,
                    capture=capture,
                    external_id=ref.external_id,
                    object_key=key,
                    reported_sha256=digest,
                    object_store=store,
                    mime_type=ref.mime_type or "application/pdf",
                )
            except autos_service.CaptureError:
                # item ja marcado failed (hash_mismatch/invalid_pdf); segue
                continue
        final = drv.enumerate_documents(target)
        return autos_service.finalize_capture(
            session, capture=capture, final_manifest=_manifest_input(final)
        )
    except InstanceNotFound as exc:
        # Ausência provada, não falha: o grau que o processo nunca teve é
        # selado com evidência para o `ContextoProcesso` poder fechar.
        return autos_service.mark_not_applicable(
            session,
            capture=capture,
            evidence={
                "motivo": InstanceNotFound.code,
                "fonte": "mni",
                "tribunal": target.tribunal,
                "grau": target.grau,
                "detalhe": str(exc),
            },
        )
    except ConnectorError as exc:
        if capture.status in _ACTIVE_STATUSES:
            capture.status = "failed"
            capture.error_code = exc.code
            session.flush()
        raise
