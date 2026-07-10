from sqlalchemy.exc import IntegrityError
import pytest

from app.sor import models


def _instance(db_session, seeded):
    instance = models.ProcessoInstancia(
        processo_id=seeded.id,
        escritorio_id=seeded.escritorio_id,
        sistema="PJe",
        tribunal="TJMG",
        grau="1",
        url_base="https://example.invalid/pje",
        status="active",
    )
    db_session.add(instance)
    db_session.flush()
    return instance


def test_document_external_id_is_unique_inside_instance(db_session, seeded):
    instance = _instance(db_session, seeded)
    values = dict(
        escritorio_id=seeded.escritorio_id,
        processo_id=seeded.id,
        processo_instancia_id=instance.id,
        external_id="doc-1",
        nome="Decisão.pdf",
        tipo="Decisão",
        ordem=1,
        sigiloso=False,
    )
    db_session.add(models.Documento(**values))
    db_session.flush()
    db_session.add(models.Documento(**values))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_document_versions_are_immutable_by_hash(db_session, seeded):
    instance = _instance(db_session, seeded)
    document = models.Documento(
        escritorio_id=seeded.escritorio_id,
        processo_id=seeded.id,
        processo_instancia_id=instance.id,
        external_id="doc-1",
        nome="Decisão.pdf",
        ordem=1,
        sigiloso=False,
    )
    capture = models.CapturaAutos(
        escritorio_id=seeded.escritorio_id,
        processo_instancia_id=instance.id,
        status="downloading",
        generation=1,
    )
    db_session.add_all([document, capture])
    db_session.flush()
    version = models.DocumentoArquivo(
        documento_id=document.id,
        captura_id=capture.id,
        sha256="a" * 64,
        storage_key="tenant/1/doc.pdf",
        uri="s3://private/doc.pdf",
        mime_type="application/pdf",
        size_bytes=100,
        extraction_status="pending",
        atual=True,
    )
    db_session.add(version)
    db_session.flush()
    assert version.atual is True
