from sqlalchemy import select

from app.sor import models
from tests.test_autos_upload_api import PDF_OK, PDF_OUTRO, _arquivo, local_store as local_store


def test_complement_preserves_inventory_links_task_and_versions(client, db_session, seeded, local_store):
    url = f"/processos/{seeded.id}/autos/upload"
    assert client.post(url, files=[_arquivo("inicial.pdf")]).status_code == 200
    task = client.post("/tarefas", json={"titulo": "Solicitar comprovante", "tipo": "documento", "processo_id": seeded.id}).json()
    result = client.post(url, data={"complementar": "true", "tarefa_id": task["id"], "tarefa_versao": 1},
                         files=[_arquivo("comprovante.pdf")])
    assert result.status_code == 200, result.text
    assert result.json()["expected_count"] == 2
    listing = client.get("/documentos", params={"processo_id": seeded.id}).json()
    assert listing["total"] == 2
    assert all(d["no_contexto"] for d in listing["items"])
    receipt = client.get(f"/tarefas/{task['id']}/documentos").json()[0]
    assert receipt["nome"] == "comprovante.pdf" and receipt["documento_arquivo_id"]
    updated = client.get("/tarefas").json()["items"][0]
    assert updated["status"] == "em_andamento" and updated["versao"] == 2
    assert client.get(f"/processos/{seeded.id}/autos/status").json()["contexto"]["ready"] is False
    result = client.post(url, data={"complementar": "true"}, files=[_arquivo("comprovante.pdf", PDF_OUTRO)])
    assert result.status_code == 200 and result.json()["expected_count"] == 2
    versions = client.get(f"/documentos/{receipt['documento_id']}/versoes").json()
    assert versions["total"] == 2
    old = client.get(f"/documentos/{receipt['documento_id']}/versoes/{receipt['documento_arquivo_id']}/conteudo")
    assert old.status_code == 200 and old.content == PDF_OK
    assert client.get(f"/tarefas/{task['id']}/documentos").json()[0]["documento_arquivo_id"] == receipt["documento_arquivo_id"]


def test_stale_or_mismatched_task_rejects_upload_atomically(client, db_session, seeded, local_store):
    task = client.post("/tarefas", json={"titulo": "Conferir", "processo_id": seeded.id}).json()
    client.patch(f"/tarefas/{task['id']}", json={"versao": 1, "status": "aguardando"})
    response = client.post(f"/processos/{seeded.id}/autos/upload",
        data={"complementar": "true", "tarefa_id": task["id"], "tarefa_versao": 1}, files=[_arquivo("teste.pdf")])
    assert response.status_code == 409
    assert db_session.scalars(select(models.Documento)).first() is None
    other = models.Processo(escritorio_id=seeded.escritorio_id, numero="outro")
    db_session.add(other)
    db_session.commit()
    response = client.post(f"/processos/{other.id}/autos/upload",
        data={"complementar": "true", "tarefa_id": task["id"], "tarefa_versao": 2}, files=[_arquivo("teste.pdf")])
    assert response.status_code == 422


def test_library_is_paginated_and_tenant_scoped(client, db_session, seeded, local_store):
    assert client.post(f"/processos/{seeded.id}/autos/upload", files=[_arquivo("a.pdf"), _arquivo("b.pdf")]).status_code == 200
    office = models.Escritorio(nome="Outro")
    db_session.add(office)
    db_session.flush()
    document = models.Documento(escritorio_id=office.id, nome="Privado")
    db_session.add(document)
    db_session.commit()
    result = client.get("/documentos", params={"limit": 1, "offset": 1}).json()
    assert result["total"] == 2 and len(result["items"]) == 1
    assert client.get(f"/documentos/{document.id}/versoes").status_code == 404
    assert client.get(f"/documentos/{document.id}/versoes/1/trechos").status_code == 404


def test_complement_rejects_incomplete_base(client, db_session, seeded, local_store):
    first = client.post(f"/processos/{seeded.id}/autos/upload", files=[_arquivo("a.pdf")]).json()
    capture = db_session.get(models.CapturaAutos, first["id"])
    capture.status = "incomplete"
    db_session.commit()
    response = client.post(f"/processos/{seeded.id}/autos/upload", data={"complementar": "true"}, files=[_arquivo("b.pdf")])
    assert response.status_code == 409
    assert len(db_session.scalars(select(models.CapturaAutos)).all()) == 1


def test_failed_batch_does_not_change_context_or_task(client, db_session, seeded, local_store):
    url = f"/processos/{seeded.id}/autos/upload"
    first = client.post(url, files=[_arquivo("inicial.pdf")]).json()
    task = client.post("/tarefas", json={"titulo": "Solicitar comprovante", "processo_id": seeded.id}).json()
    response = client.post(url, data={"complementar": "true", "tarefa_id": task["id"], "tarefa_versao": 1},
        files=[_arquivo("bom.pdf"), _arquivo("invalido.pdf", b"<html>invalid</html>")])
    assert response.status_code == 422
    assert client.get("/documentos").json()["total"] == 1
    assert client.get(f"/tarefas/{task['id']}").json()["versao"] == 1
    assert client.get(f"/tarefas/{task['id']}/documentos").json() == []
    assert [c.id for c in db_session.scalars(select(models.CapturaAutos))] == [first["id"]]


def test_supplement_worker_updates_context_and_cited_pages(client, db_session, seeded, local_store, monkeypatch):
    import re
    from pathlib import Path
    from sqlalchemy.orm import sessionmaker
    from app.autos.worker import process_due_documents
    from app.autos.summarizer import ChunkCitation, DocumentDigest

    class Provider:
        calls = 0

        def complete_structured(self, *, user, **kw):
            self.calls += 1
            chunk_id = int(re.search(r"chunk_id=(\d+)", user).group(1))
            quote = user.split("]\n", 1)[1].split("\n\n[chunk_id=", 1)[0][:60]
            return DocumentDigest(resumo="Resumo citado", fatos=[], pedidos=[], decisoes=[], prazos=[],
                incertezas=[], citations=[ChunkCitation(chunk_id=chunk_id, quote=quote)])

    provider = Provider()
    monkeypatch.setattr("app.autos.summarizer.get_provider", lambda **kw: provider)
    pdf = (Path(__file__).parent / "fixtures/pdfs/textual.pdf").read_bytes()
    url = f"/processos/{seeded.id}/autos/upload"
    assert client.post(url, files=[_arquivo("inicial.pdf", pdf)]).status_code == 200
    assert client.post(f"/processos/{seeded.id}/autos/nao-aplicavel",
        json={"grau": "2", "justificativa": "Caso de teste sem recurso em segundo grau"}).status_code == 200
    factory = sessionmaker(bind=db_session.get_bind(), expire_on_commit=False)
    assert process_due_documents(factory, backoff_seconds=0) == 1
    db_session.expire_all()
    assert client.get(f"/processos/{seeded.id}/autos/status").json()["contexto"]["ready"] is True
    assert client.post(url, data={"complementar": "true"}, files=[_arquivo("comprovante.pdf", pdf)]).status_code == 200
    assert client.get(f"/processos/{seeded.id}/autos/status").json()["contexto"]["ready"] is False
    assert process_due_documents(factory, backoff_seconds=0) == 1
    db_session.expire_all()
    context = client.get(f"/processos/{seeded.id}/autos/status").json()["contexto"]
    assert context["ready"] is True and context["documents_summarized"] == 2 and provider.calls == 2
    document = client.get("/documentos", params={"q": "comprovante"}).json()["items"][0]
    evidence_url = f"/documentos/{document['id']}/versoes/{document['versao']['id']}/trechos"
    evidence = client.get(evidence_url).json()
    assert evidence["resumo"] == "Resumo citado" and evidence["citations"][0]["pagina"] == 1
    assert evidence["items"][0]["texto"]
    assert client.get(evidence_url, params={"q": "palavra-nao-existente", "offset": 0}).json()["total"] == 0
    assert "storage_key" not in str(evidence)
    repeated = client.post(url, data={"complementar": "true"}, files=[_arquivo("comprovante.pdf", pdf)])
    assert repeated.status_code == 200
    assert repeated.json()["captured_count"] == repeated.json()["expected_count"] == 2
    assert process_due_documents(factory, backoff_seconds=0) == 0
