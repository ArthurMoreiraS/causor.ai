"""Autos entregues pelo próprio advogado.

O caminho que não depende de tribunal nenhum: o advogado baixa os autos onde já
tem acesso e envia ao Causor. Reusa as mesmas quatro etapas do agente local
(``open_capture`` → ``record_initial_manifest`` → ``confirm_document_upload`` →
``finalize_capture``), então hash recomputado, PDF validado por magic bytes,
versão imutável por SHA-256 e extração fora do request continuam valendo.

**O que muda, e precisa continuar visível.** Numa captura de tribunal,
``complete`` afirma *"o tribunal listou N peças e nós temos as N"* — a
enumeração vem de fora e a dupla conferência tem valor probatório. Aqui as duas
enumerações são a mesma lista que o advogado entregou, então ``complete`` afirma
apenas *"recebemos exatamente estes arquivos, íntegros"*. A completude passa a
ser **declarada**, e isso fica gravado em ``evidence`` e no ``fonte`` da
captura. Apagar essa distinção seria vender como prova algo que é declaração.

A identidade do documento lógico é o **nome do arquivo**: reenviar
``inicial.pdf`` corrigido cria uma versão nova do mesmo documento, não um
documento novo — que é para o que o versionamento por hash existe.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256 as sha256_digest

from sqlalchemy.orm import Session

from app.autos import service as autos_service
from app.autos.conferencia import ConsultaDatajud, conferir_upload_com_datajud
from app.autos.contracts import ManifestDocumentInput, ManifestInput
from app.sor import models
from app.storage.objects import ObjectStore

FONTE = "upload"


@dataclass(frozen=True)
class ArquivoEnviado:
    nome: str
    conteudo: bytes
    mime_type: str = "application/pdf"


def _external_id(nome: str) -> str:
    return f"upload:{nome}"


def _montar_manifesto(
    arquivos: list[ArquivoEnviado], *, usuario_id: int | None
) -> ManifestInput:
    documents = [
        ManifestDocumentInput(
            external_id=_external_id(arquivo.nome),
            nome=arquivo.nome,
            tipo=None,
            ordem=ordem,
            parent_external_id=None,
            data_documento=None,
            sigiloso=False,
            mime_type=arquivo.mime_type,
            size_hint=len(arquivo.conteudo),
            download_ref=_external_id(arquivo.nome),
        )
        for ordem, arquivo in enumerate(arquivos, start=1)
    ]
    return ManifestInput(
        cursor_complete=True,
        documents=documents,
        evidence={
            "origem": "upload_advogado",
            # Não é a mesma promessa da captura de tribunal — ver docstring.
            "completude": "declarada_pelo_advogado",
            "declarado_por_usuario_id": usuario_id,
            "arquivos": len(documents),
            "recebido_em": datetime.now(timezone.utc).isoformat(),
        },
    )


def ingerir_autos_enviados(
    session: Session,
    *,
    processo_instancia: models.ProcessoInstancia,
    usuario_id: int | None,
    arquivos: list[ArquivoEnviado],
    object_store: ObjectStore,
    datajud: ConsultaDatajud | None = None,
) -> models.CapturaAutos:
    """Transforma os arquivos entregues numa captura verificada dos autos."""
    if not arquivos:
        raise ValueError("nenhum arquivo enviado")
    nomes = [arquivo.nome for arquivo in arquivos]
    if len(set(nomes)) != len(nomes):
        raise ValueError("nomes de arquivo repetidos no mesmo envio")

    capture = autos_service.open_capture(
        session,
        processo_instancia=processo_instancia,
        usuario_id=usuario_id,
        fonte=FONTE,
    )
    manifesto = _montar_manifesto(arquivos, usuario_id=usuario_id)
    autos_service.record_initial_manifest(session, capture=capture, manifest=manifesto)

    for arquivo in arquivos:
        digest = sha256_digest(arquivo.conteudo).hexdigest()
        key = (
            f"tenant/{capture.escritorio_id}"
            f"/process/{processo_instancia.processo_id}"
            f"/instance/{processo_instancia.id}/upload/{digest}.bin"
        )
        object_store.put_bytes(key, arquivo.conteudo, arquivo.mime_type)
        autos_service.confirm_document_upload(
            session,
            capture=capture,
            external_id=_external_id(arquivo.nome),
            object_key=key,
            reported_sha256=digest,
            object_store=object_store,
            mime_type=arquivo.mime_type,
        )

    # A enumeração final é a mesma da inicial por construção; a conferência
    # segue rodando porque é ela que valida que todo item ficou `verified`.
    capture = autos_service.finalize_capture(
        session, capture=capture, final_manifest=manifesto
    )
    if datajud is not None:
        # Sinal externo, opcional por desenho: sem cliente injetado o upload
        # continua funcionando exatamente como antes. Ver `autos/conferencia.py`
        # — a completude segue declarada, isto só a confronta com o DataJud.
        conferir_upload_com_datajud(
            session,
            capture=capture,
            processo=processo_instancia.processo,
            arquivos_recebidos=len(arquivos),
            datajud=datajud,
        )
    return capture
