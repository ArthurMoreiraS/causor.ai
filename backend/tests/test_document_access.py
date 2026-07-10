from hashlib import sha256

import pytest

from app.autos.contracts import ManifestDocumentInput, ManifestInput
from app.autos.service import (
    confirm_document_upload,
    open_capture,
    record_initial_manifest,
)
from app.autos.worker import enqueue_process_purge, run_purge_process_objects_job
from app.sor import models
from app.storage.objects import LocalObjectStore


@pytest.fixture
def local_store(tmp_path, monkeypatch):
    from app import settings as settings_module

    monkeypatch.setattr(settings_module.settings, "object_store_provider", "localdev")
    monkeypatch.setattr(settings_module.settings, "object_store_local_path", str(tmp_path))
    return LocalObjectStore(tmp_path)


def _capture_with_file(db_session, seeded, store, external_id="a"):
    instancia = models.ProcessoInstancia(
        processo_id=seeded.id,
        escritorio_id=seeded.escritorio_id,
        sistema="PJe",
        tribunal="TJSP",
        grau="1",
        status="active",
    )
    db_session.add(instancia)
    db_session.flush()
    manifest = ManifestInput(
        cursor_complete=True,
        documents=[
            ManifestDocumentInput(
                external_id=external_id,
                nome="Decisão.pdf",
                tipo="Decisão",
                ordem=1,
                parent_external_id=None,
                data_documento=None,
                sigiloso=False,
                mime_type="application/pdf",
                size_hint=None,
                download_ref=f"opaque:{external_id}",
            )
        ],
        evidence={},
    )
    capture = open_capture(db_session, processo_instancia=instancia, usuario_id=1)
    record_initial_manifest(db_session, capture=capture, manifest=manifest)
    data = b"%PDF-1.4\nconteudo\n%%EOF\n"
    key = (
        f"tenant/{seeded.escritorio_id}/process/{seeded.id}/instance/{instancia.id}"
        f"/document/{capture.items[0].documento_id}/{sha256(data).hexdigest()}.bin"
    )
    store.put_bytes(key, data, "application/pdf")
    version = confirm_document_upload(
        db_session,
        capture=capture,
        external_id=external_id,
        object_key=key,
        reported_sha256=sha256(data).hexdigest(),
        object_store=store,
    )
    return version, data


@pytest.fixture
def owned_process_with_files(db_session, seeded, local_store):
    _capture_with_file(db_session, seeded, local_store)
    return seeded


@pytest.fixture
def other_tenant_document(db_session, seeded, local_store):
    other = models.Escritorio(nome="Outro escritório")
    db_session.add(other)
    db_session.flush()
    processo = models.Processo(
        escritorio_id=other.id, numero="99999990020248260100", tribunal="TJSP"
    )
    db_session.add(processo)
    db_session.flush()
    documento = models.Documento(
        escritorio_id=other.id,
        processo_id=processo.id,
        nome="Sigiloso.pdf",
        tipo="Decisão",
    )
    db_session.add(documento)
    db_session.flush()
    return documento


def test_other_tenant_cannot_get_document_download_ticket(client, other_tenant_document):
    response = client.post(f"/documentos/{other_tenant_document.id}/download-ticket")
    assert response.status_code == 404


def test_download_ticket_exposes_only_safe_fields_and_audits(
    client, db_session, seeded, local_store
):
    version, _data = _capture_with_file(db_session, seeded, local_store)
    db_session.commit()

    response = client.post(f"/documentos/{version.documento_id}/download-ticket")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"url", "expires_in", "nome", "mime_type"}
    assert body["expires_in"] == 300
    assert "storage_key" not in str(body)

    audit = (
        db_session.query(models.AuditLog)
        .filter_by(acao="document_download_ticket_created")
        .one()
    )
    # A URL assinada nunca é persistida na auditoria.
    assert "url" not in (audit.detalhe or {})


def test_localdev_content_route_streams_bytes_and_is_tenant_scoped(
    client, db_session, seeded, local_store, other_tenant_document
):
    version, data = _capture_with_file(db_session, seeded, local_store)
    db_session.commit()

    ok = client.get(f"/documentos/{version.documento_id}/conteudo")
    assert ok.status_code == 200
    assert ok.content == data

    cross = client.get(f"/documentos/{other_tenant_document.id}/conteudo")
    assert cross.status_code == 404


def test_process_delete_enqueues_object_purge(db_session, owned_process_with_files):
    enqueue_process_purge(db_session, processo=owned_process_with_files, actor="usuario:1")
    job = db_session.query(models.JobExecucao).filter_by(tipo="purge_process_objects").one()
    assert job.payload == {"processo_id": owned_process_with_files.id}


def test_purge_job_deletes_objects_in_batches_and_audits(
    db_session, seeded, local_store
):
    version, _data = _capture_with_file(db_session, seeded, local_store)
    assert local_store.get_bytes(version.storage_key)

    result = run_purge_process_objects_job(
        db_session, processo_id=seeded.id, object_store=local_store, batch_size=100
    )
    assert result["deleted"] == 1

    with pytest.raises(FileNotFoundError):
        local_store.get_bytes(version.storage_key)

    audit = (
        db_session.query(models.AuditLog)
        .filter_by(acao="process_objects_purged")
        .one()
    )
    assert audit.detalhe["deleted"] == 1
    assert audit.detalhe["sha256"] == [version.sha256]
