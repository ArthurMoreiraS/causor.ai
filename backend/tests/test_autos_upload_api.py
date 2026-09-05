"""`POST /processos/{id}/autos/upload` — o advogado entrega os autos.

É o único caminho de captura que não exige nada de tribunal: sem pareamento,
sem credencial, sem conector. Existe para o piloto poder rodar em qualquer
tribunal do país e para a demonstração caber num "me manda o PDF".
"""

import pytest

from app.sor import models

PDF_OK = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"
PDF_OUTRO = b"%PDF-1.4\n2 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"
HTML_DISFARCADO = b"<html><body>nao sou um PDF</body></html>"


@pytest.fixture
def local_store(tmp_path, monkeypatch):
    from app import settings as settings_module

    monkeypatch.setattr(settings_module.settings, "object_store_provider", "localdev")
    monkeypatch.setattr(settings_module.settings, "object_store_local_path", str(tmp_path))
    return tmp_path


def _arquivo(nome, conteudo=PDF_OK):
    return ("arquivos", (nome, conteudo, "application/pdf"))


def test_upload_worker_builds_context_and_retry_preserves_summary(
    client, db_session, seeded, local_store, monkeypatch
):
    from pathlib import Path
    from sqlalchemy.orm import sessionmaker
    from app.autos.worker import process_due_documents
    from app.autos.summarizer import DocumentDigest, ChunkCitation

    class Provider:
        calls = 0

        def complete_structured(self, *, user, **kwargs):
            import re
            self.calls += 1
            chunk_id = int(re.search(r"chunk_id=(\d+)", user).group(1))
            chunk = db_session.get(models.DocumentoTrecho, chunk_id)
            return DocumentDigest(
                resumo="Documento de teste", fatos=[], pedidos=[], decisoes=[],
                prazos=[], incertezas=[],
                citations=[ChunkCitation(chunk_id=chunk_id, quote=chunk.texto[:60])],
            )

    provider = Provider()
    monkeypatch.setattr("app.autos.summarizer.get_provider", lambda **kw: provider)
    pdf = (Path(__file__).parent / "fixtures/pdfs/textual.pdf").read_bytes()
    assert client.post(
        f"/processos/{seeded.id}/autos/upload",
        files=[_arquivo("autos.pdf", pdf)], data={"grau": "1"},
    ).status_code == 200
    declaration = client.post(
        f"/processos/{seeded.id}/autos/nao-aplicavel",
        json={"grau": "2", "justificativa": "Conferi o tribunal: não existe recurso ou autos de segundo grau."},
    )
    assert declaration.status_code == 200
    before = client.get(f"/processos/{seeded.id}/autos/status").json()
    assert before["contexto"]["ready"] is False
    factory = sessionmaker(bind=db_session.get_bind(), expire_on_commit=False)
    assert process_due_documents(factory, backoff_seconds=0) == 1
    db_session.expire_all()
    after = client.get(f"/processos/{seeded.id}/autos/status").json()
    assert after["contexto"]["ready"] is True
    assert after["contexto"]["documents_summarized"] == 1
    assert process_due_documents(factory, backoff_seconds=0) == 0
    assert provider.calls == 1

    # Continua pelos endpoints usados pelo advogado, sem inserir contexto no banco.
    from app.settings import settings
    monkeypatch.setattr(settings, "datajud_api_key", "")

    class Classifier:
        def complete_structured(self, *, schema, **kw):
            return schema(tipo="Contestação", peticao_sugerida="Contestação", prazo_dias=15,
                          dias_uteis=True, confianca=0.8, resumo="Resposta à intimação")

    class Drafter:
        def complete_structured(self, *, schema, user, **kw):
            assert "Documento de teste" in user
            assert "[DOC-" in user
            return schema(analise_providencia="Revisar a defesa", minuta="Proposta baseada nos autos.",
                          alertas=[], confianca=0.8)

    monkeypatch.setattr("app.agent.classifier.get_provider", lambda **kw: Classifier())
    monkeypatch.setattr("app.agent.drafter.get_provider", lambda **kw: Drafter())
    notice = db_session.query(models.Intimacao).first()
    draft = client.post(f"/intimacoes/{notice.id}/draft")
    assert draft.status_code == 200
    petition = draft.json()["peticao"]
    citation = petition["dossie"]["citations"][0]
    original = client.get(f"/documentos/{citation['documento_id']}/versoes/{citation['documento_arquivo_id']}/conteudo")
    assert original.content == pdf
    preview = client.get(f"/peticoes/{petition['id']}/pdf")
    assert preview.content.startswith(b"%PDF")
    assert client.post(f"/peticoes/{petition['id']}/approve").status_code == 200
    assert client.get(f"/peticoes/{petition['id']}/pdf").content == preview.content
    filed = client.post(f"/peticoes/{petition['id']}/protocolar/confirmar", json={"protocolo": "DECLARACAO-TESTE"})
    assert filed.status_code == 200
    receipt = filed.json()["dossie"]["protocolo_registrado"]
    assert receipt["origem"] == "declaracao_manual"
    assert receipt["comprovante_status"] == "ausente"


def test_general_worker_leaves_document_jobs_for_document_worker(db_session, seeded):
    from app.queue.worker import claim_next_job
    job = models.JobExecucao(tipo="process_document", status="queued", payload={})
    db_session.add(job)
    db_session.commit()
    assert claim_next_job(db_session) is None
    assert job.status == "queued"


def test_retry_recovers_legacy_extraction_only_jobs(client, db_session, seeded, local_store):
    client.post(f"/processos/{seeded.id}/autos/upload", files=[_arquivo("autos.pdf")])
    job = db_session.query(models.JobExecucao).filter_by(tipo="process_document").one()
    job.status = "completed"  # estado legado: só extração, sem resumo/contexto
    db_session.commit()
    retried = client.post(f"/processos/{seeded.id}/autos/reprocessar")
    assert retried.json() == {"reenfileirados": 1}
    assert client.post(f"/processos/{seeded.id}/autos/reprocessar").json() == {"reenfileirados": 0}
    db_session.refresh(job)
    assert job.status == "queued"


def test_envio_registra_captura_completa(client, seeded, local_store):
    resp = client.post(
        f"/processos/{seeded.id}/autos/upload",
        files=[_arquivo("inicial.pdf"), _arquivo("sentenca.pdf", PDF_OUTRO)],
        data={"grau": "1"},
    )

    assert resp.status_code == 200
    corpo = resp.json()
    assert corpo["status"] == "complete"
    assert corpo["fonte"] == "upload"
    assert corpo["expected_count"] == 2
    assert corpo["captured_count"] == 2


def test_envio_aparece_no_status_dos_autos(client, seeded, local_store):
    client.post(
        f"/processos/{seeded.id}/autos/upload",
        files=[_arquivo("inicial.pdf")],
        data={"grau": "1"},
    )

    status = client.get(f"/processos/{seeded.id}/autos/status").json()
    instancias = [i for i in status["instancias"] if i["captura"]]

    assert instancias
    assert instancias[0]["captura"]["fonte"] == "upload"


def test_pdf_falso_devolve_erro_de_dominio(client, seeded, local_store):
    resp = client.post(
        f"/processos/{seeded.id}/autos/upload",
        files=[_arquivo("falso.pdf", HTML_DISFARCADO)],
        data={"grau": "1"},
    )

    assert resp.status_code == 422
    assert resp.json()["detail"] == "invalid_pdf"


def test_envio_sem_arquivo_e_recusado(client, seeded, local_store):
    resp = client.post(f"/processos/{seeded.id}/autos/upload", data={"grau": "1"})

    assert resp.status_code == 422


def test_processo_de_outro_escritorio_nao_recebe_upload(
    client, db_session, seeded, local_store
):
    outro = models.Escritorio(nome="Outro")
    db_session.add(outro)
    db_session.flush()
    alheio = models.Processo(
        escritorio_id=outro.id, numero="99999990020248260100", tribunal="TJSP"
    )
    db_session.add(alheio)
    db_session.commit()

    resp = client.post(
        f"/processos/{alheio.id}/autos/upload",
        files=[_arquivo("inicial.pdf")],
        data={"grau": "1"},
    )

    assert resp.status_code == 404


def test_resposta_traz_a_conferencia_contra_o_datajud(client, seeded, local_store):
    """A tela precisa saber que o tribunal registra mais juntadas do que chegou.

    É sinal, não prova: a captura continua `complete`, porque o que ela afirma
    ("recebemos exatamente estes arquivos, íntegros") continua verdadeiro.
    """
    from app.api.autos_routes import get_datajud_client
    from app.capture.datajud import MovimentoDTO, ProcessoDTO

    class _DatajudComJuntadas:
        def consultar_processo(self, numero_processo: str, *, tribunal: str):
            return ProcessoDTO(
                numero_processo=numero_processo,
                movimentos=[
                    MovimentoDTO(nome="Juntada de Petição"),
                    MovimentoDTO(nome="Juntada de Documento"),
                    MovimentoDTO(nome="Conclusão"),
                ],
            )

    client.app.dependency_overrides[get_datajud_client] = _DatajudComJuntadas

    resp = client.post(
        f"/processos/{seeded.id}/autos/upload",
        files=[_arquivo("inicial.pdf")],
        data={"grau": "1"},
    )

    assert resp.status_code == 200
    corpo = resp.json()
    assert corpo["status"] == "complete"
    conferencia = corpo["conferencia_datajud"]
    assert conferencia["juntadas"] == 2
    assert conferencia["arquivos_recebidos"] == 1
    assert conferencia["divergencia"] is True


def test_arquivo_acima_do_limite_e_recusado(client, seeded, local_store, monkeypatch):
    from app import settings as settings_module

    monkeypatch.setattr(settings_module.settings, "agent_max_upload_bytes", 10)

    resp = client.post(
        f"/processos/{seeded.id}/autos/upload",
        files=[_arquivo("grande.pdf", PDF_OK)],
        data={"grau": "1"},
    )

    assert resp.status_code == 413
