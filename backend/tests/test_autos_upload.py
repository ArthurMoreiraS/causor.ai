"""Ingestão dos autos enviados pelo próprio advogado.

Este é o caminho que não depende de tribunal nenhum: o advogado baixa os autos
onde ele já tem acesso e entrega ao Causor. O pipeline de integridade é o mesmo
do agente local — hash recomputado, PDF validado por magic bytes, versão
imutável por SHA-256, extração enfileirada fora do request.

A diferença que **não pode** desaparecer: numa captura de tribunal, `complete`
significa "o tribunal listou N peças e temos as N". Num upload, a lista é a que
o advogado entregou. A completude passa a ser *declarada*, e isso fica
registrado na evidência — senão o upload contamina a prova de completude em vez
de destravá-la.
"""

import pytest

from app.autos.upload import ArquivoEnviado, ingerir_autos_enviados
from app.sor import models
from app.storage.objects import LocalObjectStore

PDF_OK = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"
PDF_OUTRO = b"%PDF-1.4\n2 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"
HTML_DISFARCADO = b"<html><body>nao sou um PDF</body></html>"


def _pdf(nome: str, conteudo: bytes = PDF_OK) -> ArquivoEnviado:
    return ArquivoEnviado(nome=nome, conteudo=conteudo, mime_type="application/pdf")


@pytest.fixture
def store(tmp_path):
    return LocalObjectStore(tmp_path)


@pytest.fixture
def instancia(db_session):
    esc = models.Escritorio(nome="Escritório Upload")
    db_session.add(esc)
    db_session.flush()
    usuario = models.Usuario(
        escritorio_id=esc.id,
        nome="Adv",
        email="adv@example.com",
        supabase_user_id="sub-upload",
    )
    db_session.add(usuario)
    processo = models.Processo(
        escritorio_id=esc.id,
        numero="10003333820184014300",
        tribunal="TRF1",
        sistema="PJe",
    )
    db_session.add(processo)
    db_session.flush()
    inst = models.ProcessoInstancia(
        processo_id=processo.id,
        escritorio_id=esc.id,
        sistema="PJe",
        tribunal="TRF1",
        grau="1",
    )
    db_session.add(inst)
    db_session.flush()
    return inst, usuario


@pytest.fixture
def ingerir(db_session, instancia, store):
    inst, usuario = instancia

    def _run(arquivos):
        return ingerir_autos_enviados(
            db_session,
            processo_instancia=inst,
            usuario_id=usuario.id,
            arquivos=arquivos,
            object_store=store,
        )

    return _run


def test_autos_enviados_viram_captura_completa(ingerir):
    capture = ingerir([_pdf("inicial.pdf"), _pdf("sentenca.pdf", PDF_OUTRO)])

    assert capture.status == "complete"
    assert capture.fonte == "upload"
    assert capture.expected_count == 2
    assert capture.captured_count == 2
    assert capture.missing_count == 0


def test_a_completude_fica_registrada_como_declarada(ingerir):
    """A prova é mais fraca que a do tribunal e o registro precisa dizer isso."""
    capture = ingerir([_pdf("inicial.pdf")])

    assert capture.evidence["initial"]["origem"] == "upload_advogado"
    assert capture.evidence["initial"]["completude"] == "declarada_pelo_advogado"


def test_pdf_falso_e_recusado_como_no_caminho_do_agente(ingerir):
    from app.autos.service import CaptureError

    with pytest.raises(CaptureError) as exc:
        ingerir([_pdf("falso.pdf", HTML_DISFARCADO)])

    # O código canônico é o contrato; a mensagem é livre.
    assert exc.value.code == "invalid_pdf"


def test_reenviar_o_mesmo_nome_cria_nova_versao_do_mesmo_documento(
    db_session, instancia, ingerir
):
    """Peça corrigida é versão nova, não documento novo — a identidade é o nome."""
    inst, _ = instancia
    ingerir([_pdf("inicial.pdf")])
    ingerir([_pdf("inicial.pdf", PDF_OUTRO)])

    documentos = (
        db_session.query(models.Documento)
        .filter(models.Documento.processo_instancia_id == inst.id)
        .all()
    )
    assert len(documentos) == 1

    versoes = (
        db_session.query(models.DocumentoArquivo)
        .filter(models.DocumentoArquivo.documento_id == documentos[0].id)
        .all()
    )
    assert len(versoes) == 2
    assert [v.atual for v in versoes].count(True) == 1


def test_extracao_e_enfileirada_para_cada_arquivo(db_session, ingerir):
    ingerir([_pdf("a.pdf"), _pdf("b.pdf", PDF_OUTRO)])

    jobs = (
        db_session.query(models.JobExecucao)
        .filter(models.JobExecucao.tipo == "process_document")
        .all()
    )
    assert len(jobs) == 2


def test_upload_sem_arquivo_e_recusado(ingerir):
    with pytest.raises(ValueError):
        ingerir([])


def test_upload_nao_enfileira_comando_para_o_agente(db_session, ingerir):
    """Os bytes já chegaram: não há nada para o computador do advogado fazer."""
    ingerir([_pdf("a.pdf")])

    assert db_session.query(models.AgentCommand).count() == 0
