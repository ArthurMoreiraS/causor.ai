from hashlib import sha256

import pytest

from app.sor import models


@pytest.fixture
def agent_headers(client):
    code = client.post("/agent/pairing-codes").json()["code"]
    paired = client.post(
        "/agent/pair",
        json={"code": code, "installation_name": "Notebook jurídico", "version": "0.1.0"},
    ).json()
    return {"Authorization": f"Agent {paired['token']}"}


@pytest.fixture
def local_store(tmp_path, monkeypatch):
    from app import settings as settings_module

    monkeypatch.setattr(settings_module.settings, "object_store_provider", "localdev")
    monkeypatch.setattr(settings_module.settings, "object_store_local_path", str(tmp_path))
    return tmp_path


def _manifest_json(order=("a", "b")):
    return {
        "cursor_complete": True,
        "documents": [
            {
                "external_id": value,
                "nome": f"{value}.pdf",
                "tipo": None,
                "ordem": index,
                "parent_external_id": None,
                "data_documento": None,
                "sigiloso": False,
                "mime_type": "application/pdf",
                "size_hint": None,
                "download_ref": f"opaque:{value}",
            }
            for index, value in enumerate(order, start=1)
        ],
        "evidence": {},
    }


def test_capture_flow_end_to_end(client, db_session, seeded, agent_headers, local_store):
    captures = client.post(f"/processos/{seeded.id}/autos/capturar", json={"graus": ["1"]})
    assert captures.status_code == 200
    capture_id = captures.json()[0]["id"]

    initial = client.put(
        f"/agent/captures/{capture_id}/manifest/initial",
        headers=agent_headers,
        json=_manifest_json(),
    )
    assert initial.status_code == 200
    assert initial.json()["status"] == "downloading"

    for external_id in ("a", "b"):
        data = b"%PDF-1.4\n" + external_id.encode() + b"\n%%EOF\n"
        digest = sha256(data).hexdigest()
        ticket = client.post(
            f"/agent/captures/{capture_id}/documents/{external_id}/upload-ticket",
            headers=agent_headers,
            json={"sha256": digest, "size_bytes": len(data)},
        ).json()
        upload = client.put(
            "/agent/uploads/local",
            params={"key": ticket["key"]},
            headers={**agent_headers, **ticket["headers"]},
            content=data,
        )
        assert upload.status_code == 200
        confirm = client.post(
            f"/agent/captures/{capture_id}/documents/{external_id}/confirm",
            headers=agent_headers,
            json={"object_key": ticket["key"], "sha256": digest},
        )
        assert confirm.status_code == 200
        assert confirm.json()["status"] == "verified"

    final = client.put(
        f"/agent/captures/{capture_id}/manifest/final",
        headers=agent_headers,
        json=_manifest_json(),
    )
    assert final.status_code == 200
    assert final.json()["status"] == "complete"

    status = client.get(f"/processos/{seeded.id}/autos/status").json()
    assert status["instancias"][0]["captura"]["status"] == "complete"


def test_changed_final_manifest_is_incomplete(
    client, db_session, seeded, agent_headers, local_store
):
    capture_id = client.post(
        f"/processos/{seeded.id}/autos/capturar", json={"graus": ["1"]}
    ).json()[0]["id"]
    client.put(
        f"/agent/captures/{capture_id}/manifest/initial",
        headers=agent_headers,
        json=_manifest_json(("a",)),
    )
    data = b"%PDF-1.4\na\n%%EOF\n"
    digest = sha256(data).hexdigest()
    ticket = client.post(
        f"/agent/captures/{capture_id}/documents/a/upload-ticket",
        headers=agent_headers,
        json={"sha256": digest, "size_bytes": len(data)},
    ).json()
    client.put(
        "/agent/uploads/local",
        params={"key": ticket["key"]},
        headers={**agent_headers, **ticket["headers"]},
        content=data,
    )
    client.post(
        f"/agent/captures/{capture_id}/documents/a/confirm",
        headers=agent_headers,
        json={"object_key": ticket["key"], "sha256": digest},
    )
    final = client.put(
        f"/agent/captures/{capture_id}/manifest/final",
        headers=agent_headers,
        json=_manifest_json(("a", "b")),
    )
    assert final.json()["status"] == "incomplete"
    assert final.json()["error_code"] == "manifest_changed"


def test_agent_of_other_tenant_gets_404(client, db_session, seeded, agent_headers, local_store):
    capture_id = client.post(
        f"/processos/{seeded.id}/autos/capturar", json={"graus": ["1"]}
    ).json()[0]["id"]

    other = models.Escritorio(nome="Outro escritório")
    db_session.add(other)
    db_session.flush()
    capture = db_session.get(models.CapturaAutos, capture_id)
    capture.escritorio_id = other.id
    db_session.commit()

    response = client.put(
        f"/agent/captures/{capture_id}/manifest/initial",
        headers=agent_headers,
        json=_manifest_json(),
    )
    assert response.status_code == 404


def test_capture_requires_auth(client, seeded):
    assert client.put("/agent/captures/1/manifest/initial", json=_manifest_json()).status_code == 401
