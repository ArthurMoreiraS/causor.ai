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
