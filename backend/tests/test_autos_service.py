from hashlib import sha256

import pytest

from app.autos.contracts import ManifestDocumentInput, ManifestInput
from app.autos.service import (
    CaptureError,
    confirm_document_upload,
    finalize_capture,
    open_capture,
    record_initial_manifest,
)
from app.sor import models
from app.storage.objects import LocalObjectStore


@pytest.fixture
def instance(db_session, seeded):
    row = models.ProcessoInstancia(
        processo_id=seeded.id,
        escritorio_id=seeded.escritorio_id,
        sistema="PJe",
        tribunal="TJMG",
        grau="1",
        url_base="https://example.invalid/pje",
        status="active",
    )
    db_session.add(row)
    db_session.flush()
    return row


@pytest.fixture
def object_store(tmp_path):
    return LocalObjectStore(tmp_path)


def _manifest(order=("a", "b", "c")):
    return ManifestInput(
        cursor_complete=True,
        documents=[
            ManifestDocumentInput(
                external_id=value,
                nome=f"{value}.pdf",
                tipo=None,
                ordem=index,
                parent_external_id=None,
                data_documento=None,
                sigiloso=False,
                mime_type="application/pdf",
                size_hint=None,
                download_ref=f"opaque:{value}",
            )
            for index, value in enumerate(order, start=1)
        ],
        evidence={},
    )


@pytest.fixture
def complete_manifest():
    return _manifest()


def _upload_all(db_session, capture, object_store):
    for item in capture.items:
        data = b"%PDF-1.4\n" + item.external_id.encode("utf-8") + b"\n%%EOF\n"
        digest = sha256(data).hexdigest()
        key = f"test/{item.external_id}.pdf"
        object_store.put_bytes(key, data, "application/pdf")
        confirm_document_upload(
            db_session,
            capture=capture,
            external_id=item.external_id,
            object_key=key,
            reported_sha256=digest,
            object_store=object_store,
        )


def test_capture_only_completes_after_same_final_manifest(
    db_session, seeded, instance, object_store, complete_manifest
):
    capture = open_capture(db_session, processo_instancia=instance, usuario_id=1)
    record_initial_manifest(db_session, capture=capture, manifest=complete_manifest)
    _upload_all(db_session, capture, object_store)
    result = finalize_capture(db_session, capture=capture, final_manifest=complete_manifest)
    assert result.status == "complete"
    assert result.missing_count == 0


def test_changed_final_manifest_marks_incomplete(
    db_session, seeded, instance, object_store, complete_manifest
):
    capture = open_capture(db_session, processo_instancia=instance, usuario_id=1)
    record_initial_manifest(db_session, capture=capture, manifest=complete_manifest)
    _upload_all(db_session, capture, object_store)
    result = finalize_capture(db_session, capture=capture, final_manifest=_manifest(("a", "b")))
    assert result.status == "incomplete"
    assert result.error_code == "manifest_changed"


def test_missing_download_marks_incomplete(
    db_session, seeded, instance, object_store, complete_manifest
):
    capture = open_capture(db_session, processo_instancia=instance, usuario_id=1)
    record_initial_manifest(db_session, capture=capture, manifest=complete_manifest)
    # Só sobe "a"; "b" e "c" ficam pending.
    data = b"%PDF-1.4\na\n%%EOF\n"
    object_store.put_bytes("test/a.pdf", data, "application/pdf")
    confirm_document_upload(
        db_session,
        capture=capture,
        external_id="a",
        object_key="test/a.pdf",
        reported_sha256=sha256(data).hexdigest(),
        object_store=object_store,
    )
    result = finalize_capture(db_session, capture=capture, final_manifest=complete_manifest)
    assert result.status == "incomplete"
    assert result.error_code == "items_unverified"


def test_hash_mismatch_is_rejected(db_session, seeded, instance, object_store, complete_manifest):
    capture = open_capture(db_session, processo_instancia=instance, usuario_id=1)
    record_initial_manifest(db_session, capture=capture, manifest=complete_manifest)
    data = b"%PDF-1.4\na\n%%EOF\n"
    object_store.put_bytes("test/a.pdf", data, "application/pdf")
    with pytest.raises(CaptureError) as exc:
        confirm_document_upload(
            db_session,
            capture=capture,
            external_id="a",
            object_key="test/a.pdf",
            reported_sha256="0" * 64,
            object_store=object_store,
        )
    assert exc.value.code == "hash_mismatch"


def test_html_disguised_as_pdf_is_rejected(
    db_session, seeded, instance, object_store, complete_manifest
):
    capture = open_capture(db_session, processo_instancia=instance, usuario_id=1)
    record_initial_manifest(db_session, capture=capture, manifest=complete_manifest)
    data = b"<html>sessao expirada</html>"
    object_store.put_bytes("test/a.pdf", data, "application/pdf")
    with pytest.raises(CaptureError) as exc:
        confirm_document_upload(
            db_session,
            capture=capture,
            external_id="a",
            object_key="test/a.pdf",
            reported_sha256=sha256(data).hexdigest(),
            object_store=object_store,
        )
    assert exc.value.code == "invalid_pdf"


def test_confirm_is_idempotent(db_session, seeded, instance, object_store, complete_manifest):
    capture = open_capture(db_session, processo_instancia=instance, usuario_id=1)
    record_initial_manifest(db_session, capture=capture, manifest=complete_manifest)
    data = b"%PDF-1.4\na\n%%EOF\n"
    digest = sha256(data).hexdigest()
    object_store.put_bytes("test/a.pdf", data, "application/pdf")
    first = confirm_document_upload(
        db_session,
        capture=capture,
        external_id="a",
        object_key="test/a.pdf",
        reported_sha256=digest,
        object_store=object_store,
    )
    second = confirm_document_upload(
        db_session,
        capture=capture,
        external_id="a",
        object_key="test/a.pdf",
        reported_sha256=digest,
        object_store=object_store,
    )
    assert first.id == second.id


def test_recapture_creates_new_generation_and_supersedes_versions(
    db_session, seeded, instance, object_store, complete_manifest
):
    first = open_capture(db_session, processo_instancia=instance, usuario_id=1)
    record_initial_manifest(db_session, capture=first, manifest=complete_manifest)
    _upload_all(db_session, first, object_store)
    finalize_capture(db_session, capture=first, final_manifest=complete_manifest)

    second = open_capture(db_session, processo_instancia=instance, usuario_id=1)
    assert second.generation == first.generation + 1
    record_initial_manifest(db_session, capture=second, manifest=complete_manifest)
    # Documento "a" mudou de conteúdo no portal: nova versão vira a atual.
    data = b"%PDF-1.4\na-v2\n%%EOF\n"
    object_store.put_bytes("test/a-v2.pdf", data, "application/pdf")
    version = confirm_document_upload(
        db_session,
        capture=second,
        external_id="a",
        object_key="test/a-v2.pdf",
        reported_sha256=sha256(data).hexdigest(),
        object_store=object_store,
    )
    assert version.atual is True
    older = (
        db_session.query(models.DocumentoArquivo)
        .filter(
            models.DocumentoArquivo.documento_id == version.documento_id,
            models.DocumentoArquivo.id != version.id,
        )
        .all()
    )
    assert older and all(not row.atual for row in older)
