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
        cred = service.store_court_session(
            db_session, usuario_id=u.id, sistema="PJe", tribunal="TJMG", grau="1",
            url_base="https://pje-treino.tjmg.jus.br",
            storage_state={"cookies": [{"name": "z", "value": "keep-me"}]},
        )
        cred_id = cred.id

        importlib.reload(service)  # simula reinício do processo
        payload = service.load_court_session_payload(db_session, credencial_id=cred_id)
        assert payload["storage_state"]["cookies"][0]["value"] == "keep-me"
    finally:
        monkeypatch.delenv("CAUSOR_VAULT_LOCALDEV_PATH", raising=False)
        importlib.reload(service)  # restaura modo in-memory para os demais testes
