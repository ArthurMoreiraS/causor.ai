"""Ponta a ponta real: cliente HTTP → simulador SOAP → executor → complete."""

import threading

import pytest

from app.autos import service as autos_service
from app.connectors.errors import AccessDenied
from app.connectors.mni import credentials as mni_credentials
from app.connectors.mni.client import MniClient
from app.connectors.mni.executor import run_mni_capture_job
from app.connectors.mni.reader import MniReaderDriver
from app.connectors.simulators.mni import MniSimulator, build_mni_server
from app.sor import models
from app.storage.objects import get_object_store


@pytest.fixture()
def mni_server():
    simulator = MniSimulator()
    server = build_mni_server(simulator, "127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}/intercomunicacao"
    server.shutdown()


@pytest.fixture()
def instancia_tjmg(db_session, seeded):
    processo = models.Processo(
        escritorio_id=seeded.escritorio_id,
        numero="0000000-00.2026.8.13.0000",
        tribunal="TJMG",
        sistema="PJe",
    )
    db_session.add(processo)
    db_session.flush()
    instancia = models.ProcessoInstancia(
        processo_id=processo.id, escritorio_id=seeded.escritorio_id,
        sistema="PJe", tribunal="TJMG", grau="1", status="active",
    )
    db_session.add(instancia)
    db_session.flush()
    return instancia


def _usuario_id(db_session) -> int:
    from sqlalchemy import select

    return db_session.scalars(select(models.Usuario)).first().id


def test_captura_completa_contra_simulador(db_session, seeded, instancia_tjmg, mni_server):
    mni_credentials.store_mni_credencial(
        db_session, escritorio_id=seeded.escritorio_id, usuario_id=_usuario_id(db_session),
        tribunal="TJMG", id_consultante="12345678900", senha="sim-senha",
    )
    capture = autos_service.open_capture(
        db_session, processo_instancia=instancia_tjmg, usuario_id=_usuario_id(db_session)
    )
    client = MniClient(
        url_endpoint=mni_server, id_consultante="12345678900", senha="sim-senha"
    )
    result = run_mni_capture_job(
        db_session, capture_id=capture.id, object_store=get_object_store(),
        driver=MniReaderDriver(client),
    )
    assert result.status == "complete"
    assert result.expected_count == 3
    assert result.captured_count == 3


def test_senha_errada_vira_access_denied(mni_server):
    client = MniClient(
        url_endpoint=mni_server, id_consultante="12345678900", senha="errada"
    )
    with pytest.raises(AccessDenied):
        client.consultar_processo("0000000-00.2026.8.13.0000")
