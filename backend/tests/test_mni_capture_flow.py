"""Roteamento e executor MNI: fonte certa, pipeline de integridade intacto."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.autos import service as autos_service
from app.connectors.contracts import CourtDocumentRef, CourtManifestSnapshot
from app.connectors.mni import credentials as mni_credentials
from app.connectors.mni.executor import run_mni_capture_job
from app.sor import models
from app.storage.objects import get_object_store


def _usuario_id(db_session) -> int:
    return db_session.scalars(select(models.Usuario)).first().id


@pytest.fixture()
def instancia_tjmg(db_session, seeded):
    processo = models.Processo(
        escritorio_id=seeded.escritorio_id,
        numero="0000000-00.2026.8.13.0000",
        tribunal="TRF5",
        sistema="PJe",
    )
    db_session.add(processo)
    db_session.flush()
    instancia = models.ProcessoInstancia(
        processo_id=processo.id,
        escritorio_id=seeded.escritorio_id,
        sistema="PJe",
        tribunal="TRF5",
        grau="1",
        status="active",
    )
    db_session.add(instancia)
    db_session.flush()
    return instancia


def test_open_capture_sem_credencial_usa_agente(db_session, seeded, instancia_tjmg):
    capture = autos_service.open_capture(
        db_session, processo_instancia=instancia_tjmg, usuario_id=_usuario_id(db_session)
    )
    assert capture.fonte == "agente"
    assert capture.agent_command_id is not None


def test_open_capture_com_credencial_enfileira_job_mni(db_session, seeded, instancia_tjmg):
    mni_credentials.store_mni_credencial(
        db_session, escritorio_id=seeded.escritorio_id, usuario_id=_usuario_id(db_session),
        tribunal="TRF5", id_consultante="123", senha="s",
    )
    capture = autos_service.open_capture(
        db_session, processo_instancia=instancia_tjmg, usuario_id=_usuario_id(db_session)
    )
    assert capture.fonte == "mni"
    assert capture.agent_command_id is None
    job = db_session.scalars(
        select(models.JobExecucao).where(models.JobExecucao.tipo == "mni_capture")
    ).one()
    assert job.payload["capture_id"] == capture.id


class FakeDriver:
    """Driver fake com dois documentos válidos; sem rede."""

    sistema = "MNI"

    def __init__(self):
        self._refs = (
            CourtDocumentRef(
                external_id="SIM-DOC-001", nome="Peticao.pdf", tipo="1", ordem=1,
                data_documento=None, sigiloso=False, mime_type="application/pdf",
                size_hint=None, download_ref="SIM-DOC-001",
            ),
            CourtDocumentRef(
                external_id="SIM-DOC-002", nome="Decisao.pdf", tipo="4", ordem=2,
                data_documento=None, sigiloso=False, mime_type="application/pdf",
                size_hint=None, download_ref="SIM-DOC-002",
            ),
        )

    def enumerate_documents(self, target):
        return CourtManifestSnapshot(
            target=target, documentos=self._refs, cursor_complete=True,
            source_fingerprint="sha256:fixo", captured_at=datetime.now(timezone.utc),
            evidence={"fonte": "mni", "documentos": 2, "conteudo_inline": False},
        )

    def prefetch(self, target, refs):
        return None

    def download_document(self, target, ref):
        return b"%PDF-1.4\n%" + ref.external_id.encode() + b"\n%%EOF\n"


def test_executor_completa_captura_com_prova_de_integridade(
    db_session, seeded, instancia_tjmg
):
    mni_credentials.store_mni_credencial(
        db_session, escritorio_id=seeded.escritorio_id, usuario_id=_usuario_id(db_session),
        tribunal="TRF5", id_consultante="123", senha="s",
    )
    capture = autos_service.open_capture(
        db_session, processo_instancia=instancia_tjmg, usuario_id=_usuario_id(db_session)
    )
    result = run_mni_capture_job(
        db_session, capture_id=capture.id, object_store=get_object_store(),
        driver=FakeDriver(),
    )
    assert result.status == "complete"
    assert result.captured_count == 2
    versions = db_session.scalars(select(models.DocumentoArquivo)).all()
    assert len(versions) == 2
    assert all(v.sha256 for v in versions)


def test_executor_sela_not_applicable_quando_a_instancia_nao_existe(
    db_session, seeded, instancia_tjmg
):
    """Tribunal afirmando que não há processo neste grau não é falha.

    Sem isto o processo só de 1º grau nunca fecha o `ContextoProcesso` e o
    gate fail-closed exige override em toda minuta.
    """
    from app.connectors.errors import InstanceNotFound

    class SemInstanciaDriver(FakeDriver):
        def enumerate_documents(self, target):
            raise InstanceNotFound("MNI: processo inexistente nesta instancia")

    mni_credentials.store_mni_credencial(
        db_session, escritorio_id=seeded.escritorio_id, usuario_id=_usuario_id(db_session),
        tribunal="TRF5", id_consultante="123", senha="s",
    )
    capture = autos_service.open_capture(
        db_session, processo_instancia=instancia_tjmg, usuario_id=_usuario_id(db_session)
    )

    result = run_mni_capture_job(
        db_session, capture_id=capture.id, object_store=get_object_store(),
        driver=SemInstanciaDriver(),
    )

    assert result.status == "not_applicable"
    assert result.error_code is None
    assert result.evidence["motivo"] == "instance_not_found"
    assert result.evidence["fonte"] == "mni"


def test_executor_marca_failed_em_erro_canonico(db_session, seeded, instancia_tjmg):
    from app.connectors.errors import MniUnavailable

    class BrokenDriver(FakeDriver):
        def enumerate_documents(self, target):
            raise MniUnavailable("endpoint fora")

    mni_credentials.store_mni_credencial(
        db_session, escritorio_id=seeded.escritorio_id, usuario_id=_usuario_id(db_session),
        tribunal="TRF5", id_consultante="123", senha="s",
    )
    capture = autos_service.open_capture(
        db_session, processo_instancia=instancia_tjmg, usuario_id=_usuario_id(db_session)
    )
    with pytest.raises(MniUnavailable):
        run_mni_capture_job(
            db_session, capture_id=capture.id, object_store=get_object_store(),
            driver=BrokenDriver(),
        )
    db_session.refresh(capture)
    assert capture.status == "failed"
    assert capture.error_code == "mni_unavailable"
