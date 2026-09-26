from hashlib import sha256
from io import BytesIO
from zipfile import ZipFile

import pytest

from app.agent.drafter import MinutaGerada
from app.settings import settings
from app.sor import models as m
from tests.test_legal_work import prepared_work


@pytest.fixture
def package_work(client, db_session, seeded, monkeypatch, tmp_path):
    from app.agent import work_service
    monkeypatch.setattr(settings, "object_store_provider", "localdev")
    monkeypatch.setattr(settings, "object_store_local_path", str(tmp_path / "objects"))
    work = prepared_work(client, db_session, seeded, monkeypatch)
    work = client.post(f"/trabalhos/{work['id']}/evidencias/conferir", json={"versao": work["versao"]}).json()
    monkeypatch.setattr(work_service, "draft_peticao", lambda **kwargs: MinutaGerada(contexto_consolidado="Contexto",
        analise_providencia="Análise", minuta="PETIÇÃO\nTexto revisado para demonstração.", confianca=0.5))
    work = client.post(f"/trabalhos/{work['id']}/minuta", json={"versao": work["versao"]}).json()
    return work


def make_package(client, work, seeded, **overrides):
    payload = {"versao_trabalho": work["versao"], "destino": {"tribunal": seeded.tribunal or "TJSP", "grau": "1",
        "orgao": "Vara de teste", "tipo_ato": "Manifestação"}, "anexos": []}
    payload.update(overrides)
    result = client.post(f"/trabalhos/{work['id']}/pacotes", json=payload)
    assert result.status_code == 201, result.text
    return result.json()


def approve(client, package):
    result = client.post(f"/pacotes/{package['id']}/aprovar", json={"fingerprint": package["fingerprint"]})
    assert result.status_code == 200, result.text
    return result.json()


def start_attempt(client, package):
    payload = {"fingerprint": package["fingerprint"], "idempotency_key": "external-attempt-123"}
    result = client.post(f"/pacotes/{package['id']}/tentativas", json=payload)
    assert result.status_code == 201, result.text
    return result.json()


def test_package_requires_exact_approval_and_export_preserves_bytes(client, db_session, seeded, package_work):
    package = make_package(client, package_work, seeded)
    assert "storage_key" not in str(package)
    assert client.get(f"/pacotes/{package['id']}/exportar").status_code == 409
    assert client.post(f"/pacotes/{package['id']}/aprovar", json={"fingerprint": "0" * 64}).status_code == 409
    package = approve(client, package)
    output = client.get(f"/pacotes/{package['id']}/exportar")
    assert output.status_code == 200
    with ZipFile(BytesIO(output.content)) as archive:
        data = archive.read("01-peticao.pdf")
        assert sha256(data).hexdigest() == package["items"][0]["sha256"]
    assert db_session.query(m.TentativaProtocolo).count() == 0
    assert db_session.get(m.Peticao, package_work["peticao_id"]).status == "aprovada"


def test_edit_after_approval_blocks_export_and_replacement_requires_approval(client, seeded, package_work):
    package = approve(client, make_package(client, package_work, seeded))
    assert client.patch(f"/peticoes/{package_work['peticao_id']}", json={"conteudo": "Texto editado depois"}).status_code == 200
    assert client.get(f"/pacotes/{package['id']}/exportar").status_code == 409
    newer = make_package(client, package_work, seeded)
    assert newer["versao"] == 2 and newer["aprovada_em"] is None
    assert client.get(f"/pacotes/{newer['id']}/exportar").status_code == 409


def test_attempt_deduplicates_and_never_marks_export_as_filed(client, db_session, seeded, package_work):
    package = approve(client, make_package(client, package_work, seeded))
    first = start_attempt(client, package)
    second = start_attempt(client, package)
    assert first["id"] == second["id"]
    assert first["status"] == "aguardando_envio_externo"
    assert db_session.get(m.Peticao, package_work["peticao_id"]).status == "aprovada"
    reported = client.post(f"/tentativas/{first['id']}/informar-envio", json={"versao": first["versao"], "protocolo": "DECLARADO-123", "data_ato": "2026-09-20T14:00:00-03:00"})
    assert reported.status_code == 200 and reported.json()["status"] == "envio_informado"
    assert db_session.get(m.Peticao, package_work["peticao_id"]).status == "aprovada"
    assert client.post(f"/tentativas/{first['id']}/cancelar", json={"versao": reported.json()["versao"], "motivo": "Cancelamento depois de informar envio não é seguro"}).status_code == 409


def receipt_pdf(number):
    import fitz
    with fitz.open() as document:
        page = document.new_page()
        page.insert_text((40, 50), f"COMPROVANTE\nProcesso: {number}\nProtocolo: TESTE-123")
        return document.tobytes()


def test_wrong_receipt_cannot_confirm_and_correct_receipt_requires_human_review(client, db_session, seeded, package_work):
    package = approve(client, make_package(client, package_work, seeded))
    attempt = start_attempt(client, package)
    response = client.post(f"/tentativas/{attempt['id']}/comprovantes?versao={attempt['versao']}",
        files={"arquivo": ("outro.pdf", receipt_pdf("0000123-45.2026.8.26.0100"), "application/pdf")})
    assert response.status_code == 201, response.text
    attempt = response.json()
    receipt = attempt["comprovantes"][0]
    assert receipt["status"] == "divergente"
    review = {"versao": attempt["versao"], "numero_processo": seeded.numero, "protocolo": "TESTE-123",
        "data_ato": "2026-09-20T14:00:00-03:00", "observacoes": "Conferi processo, destino e arquivos do pacote."}
    assert client.post(f"/comprovantes/{receipt['id']}/conferir", json=review).status_code == 409
    data = receipt_pdf(seeded.numero)
    response = client.post(f"/tentativas/{attempt['id']}/comprovantes?versao={attempt['versao']}",
        files={"arquivo": ("correto.pdf", data, "application/pdf")})
    assert response.status_code == 201, response.text
    attempt = response.json()
    receipt = attempt["comprovantes"][0]
    assert receipt["status"] == "recebido"
    assert client.get(f"/comprovantes/{receipt['id']}/arquivo").content == data
    assert db_session.get(m.Peticao, package_work["peticao_id"]).status == "aprovada"
    response = client.post(f"/comprovantes/{receipt['id']}/conferir", json={**review, "versao": attempt["versao"]})
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "envio_confirmado"
    assert response.json()["comprovantes"][0]["dados"]["metodo"] == "conferencia_humana"
    assert db_session.get(m.Peticao, package_work["peticao_id"]).status == "protocolada"


def test_package_and_receipts_never_cross_tenants(client, db_session, seeded, package_work):
    package = make_package(client, package_work, seeded)
    office = m.Escritorio(nome="Outro")
    db_session.add(office)
    db_session.flush()
    row = db_session.get(m.PacoteProtocolo, package["id"])
    row.escritorio_id = office.id
    db_session.commit()
    assert client.get(f"/pacotes/{row.id}/arquivos/0").status_code == 404
    assert client.get(f"/pacotes/{row.id}/exportar").status_code == 404


def test_reverting_text_does_not_restore_approval(client, db_session, seeded, package_work):
    package = approve(client, make_package(client, package_work, seeded))
    original = db_session.get(m.Peticao, package_work["peticao_id"]).conteudo
    route = f"/peticoes/{package_work['peticao_id']}"
    assert client.patch(route, json={"conteudo": "Outra versão"}).status_code == 200
    assert client.patch(route, json={"conteudo": original}).status_code == 200
    assert client.get(f"/pacotes/{package['id']}/exportar").status_code == 409
    assert client.post(f"/pacotes/{package['id']}/tentativas", json={"fingerprint": package["fingerprint"], "idempotency_key": "reverted-test-1"}).status_code == 409
    fresh = make_package(client, package_work, seeded)
    assert fresh["versao"] == 2
    approve(client, fresh)
    assert client.get(f"/pacotes/{fresh['id']}/exportar").status_code == 200


def test_active_attempt_freezes_draft_and_legacy_routes_cannot_bypass_review(client, seeded, package_work):
    package = approve(client, make_package(client, package_work, seeded))
    start_attempt(client, package)
    route = f"/peticoes/{package_work['peticao_id']}"
    assert client.patch(route, json={"conteudo": "Editado durante envio"}).status_code == 409
    assert client.post(route + "/protocolar/async").status_code == 409
    assert client.post(route + "/protocolar/confirmar", json={"protocolo": "declaração"}).status_code == 409
