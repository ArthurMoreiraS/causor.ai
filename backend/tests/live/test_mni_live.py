"""Validação live do MNI — só na máquina autorizada, nunca em CI.

Requer credenciamento aprovado no tribunal alvo e um processo do próprio
advogado seguro para leitura. Duas enumerações devem ter fingerprint
idêntico antes de qualquer promoção de perfil (verificado=True).
"""

import os

import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_MNI_LIVE") != "1",
    reason="set RUN_MNI_LIVE=1 on the authorized machine",
)


def _client():
    from app.connectors.mni.client import MniClient
    from app.connectors.mni.profiles import resolve_mni_profile

    profile = resolve_mni_profile(
        os.environ["CAUSOR_MNI_LIVE_COURT"], os.environ["CAUSOR_MNI_LIVE_DEGREE"]
    )
    assert profile is not None, "registre o perfil do tribunal antes do teste live"
    return MniClient(
        url_endpoint=profile.url_endpoint,
        id_consultante=os.environ["CAUSOR_MNI_LIVE_ID"],
        senha=os.environ["CAUSOR_MNI_LIVE_SENHA"],
    )


def test_live_consulta_lista_documentos_com_fingerprint_estavel():
    from app.connectors.contracts import CourtTarget
    from app.connectors.mni.reader import MniReaderDriver

    driver = MniReaderDriver(_client())
    target = CourtTarget(
        processo_instancia_id=0, processo_id=0,
        numero_processo=os.environ["CAUSOR_MNI_LIVE_PROCESS"],
        sistema="PJe", tribunal=os.environ["CAUSOR_MNI_LIVE_COURT"],
        grau=os.environ["CAUSOR_MNI_LIVE_DEGREE"], url_base="",
    )
    first = driver.enumerate_documents(target)
    second = driver.enumerate_documents(target)
    assert first.cursor_complete is True
    assert first.documentos, "processo live sem documentos listados"
    assert first.source_fingerprint == second.source_fingerprint
