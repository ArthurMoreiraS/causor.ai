"""The localdev vault must survive a process restart when file-backed."""

import importlib

from app.sor import models
from app.vault import service


def _usuario(db_session):
    esc = models.Escritorio(nome="Esc")
    db_session.add(esc)
    db_session.flush()
    u = models.Usuario(escritorio_id=esc.id, nome="Adv", email="a@e.com")
    db_session.add(u)
    db_session.flush()
    return u


def test_localdev_secret_survives_module_reload(db_session, tmp_path, monkeypatch):
    monkeypatch.setenv("CAUSOR_VAULT_LOCALDEV_PATH", str(tmp_path / "vault.json"))
    importlib.reload(service)
    try:
        u = _usuario(db_session)
        cred = service.store_signature_reference(
            db_session, usuario_id=u.id, provedor="BirdID",
            external_ref="adv@birdid.example",
        )
        referencia = cred.referencia_vault

        importlib.reload(service)  # simula reinício do processo
        secret = service._load_secret_from_reference(db_session, referencia)
        assert secret == "adv@birdid.example"
    finally:
        monkeypatch.delenv("CAUSOR_VAULT_LOCALDEV_PATH", raising=False)
        importlib.reload(service)  # restaura modo in-memory para os demais testes
