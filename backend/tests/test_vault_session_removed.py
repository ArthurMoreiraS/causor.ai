"""O vault de sessão de tribunal foi removido: acesso é só via agente local.

Cookies/storage_state nunca mais entram no backend; sobra no vault apenas a
referência de assinatura em nuvem (``cloud_cert``).
"""

from app.sor import models
from app.vault import service


def test_court_session_helpers_are_removed():
    for name in (
        "store_court_session",
        "find_active_session",
        "load_court_session_payload",
        "store_pje_session_reference",
        "load_pje_session_payload",
    ):
        assert not hasattr(service, name), f"{name} deveria ter sido removido"


def test_session_capture_endpoints_are_gone(client, seeded):
    resp = client.post(
        "/usuarios/1/sessoes-tribunal/capturar", json={"tribunal": "TJSP", "grau": "1"}
    )
    assert resp.status_code in (404, 405)
    resp = client.post(
        "/usuarios/1/pje-sessoes",
        json={"tribunal": "TJSP", "url_base": "https://x", "storage_state": {}},
    )
    assert resp.status_code in (404, 405)


def test_cloud_cert_credentials_still_work(db_session, seeded):
    usuario = db_session.query(models.Usuario).first()
    cred = service.store_signature_reference(
        db_session, usuario_id=usuario.id, provedor="BirdID", external_ref="ref-123"
    )
    assert cred.tipo == "cloud_cert"
    assert cred.ativo is True
