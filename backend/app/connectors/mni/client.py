"""Cliente SOAP do MNI (consultarProcesso, intercomunicação 2.2.2).

Transporte artesanal: envelope por template + parsing lxml por
``local-name()``, porque tribunais variam prefixo/namespace. Sem WSDL em
runtime — WSDL de tribunal quebrado não pode derrubar o cliente. A senha
nunca aparece em log, erro ou ``repr``.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from xml.sax.saxutils import escape

import httpx
from lxml import etree

from app.connectors.errors import (
    AccessDenied,
    DocumentDownloadFailed,
    LayoutUnknown,
    MniUnavailable,
)
from app.settings import settings

_AUTH_HINTS = ("senha", "autoriza", "credenci", "usuario", "usuário", "login")

_ENVELOPE = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" '
    'xmlns:ser="http://www.cnj.jus.br/servico-intercomunicacao-2.2.2/">'
    "<soapenv:Header/><soapenv:Body><ser:consultarProcesso>"
    "<ser:idConsultante>{id_consultante}</ser:idConsultante>"
    "<ser:senhaConsultante>{senha}</ser:senhaConsultante>"
    "<ser:numeroProcesso>{numero}</ser:numeroProcesso>"
    "<ser:movimentos>false</ser:movimentos>"
    "<ser:incluirCabecalho>true</ser:incluirCabecalho>"
    "<ser:incluirDocumentos>{incluir_documentos}</ser:incluirDocumentos>"
    "{documentos}"
    "</ser:consultarProcesso></soapenv:Body></soapenv:Envelope>"
)


@dataclass(frozen=True)
class MniDocumentoMeta:
    id: str
    tipo: str | None
    descricao: str | None
    data_hora: str | None
    mimetype: str | None
    nivel_sigilo: int
    parent_id: str | None = None


@dataclass(frozen=True)
class MniConsultaResult:
    sucesso: bool
    mensagem: str
    documentos: tuple[MniDocumentoMeta, ...]
    conteudo_inline: bool


def _sanitize_numero(numero: str) -> str:
    digits = "".join(ch for ch in numero if ch.isdigit())
    if not digits:
        raise LayoutUnknown("numero de processo vazio apos sanitizacao")
    return digits


class MniClient:
    def __init__(
        self,
        *,
        url_endpoint: str,
        id_consultante: str,
        senha: str,
        timeout: float | None = None,
        transport: httpx.BaseTransport | None = None,
    ):
        self._url = url_endpoint
        self._id = id_consultante
        self._senha = senha
        self._timeout = timeout or settings.mni_timeout_seconds
        self._transport = transport

    def __repr__(self) -> str:  # senha fora do repr, sempre
        return f"MniClient(url={self._url!r}, id_consultante={self._id!r})"

    # -- transporte -------------------------------------------------------

    def _post(self, body: str) -> bytes:
        try:
            with httpx.Client(transport=self._transport, timeout=self._timeout) as http:
                response = http.post(
                    self._url,
                    content=body.encode("utf-8"),
                    headers={
                        "Content-Type": "text/xml; charset=utf-8",
                        "SOAPAction": "consultarProcesso",
                    },
                )
        except httpx.HTTPError as exc:
            raise MniUnavailable(f"falha de transporte MNI: {type(exc).__name__}") from exc
        if response.status_code >= 500:
            raise MniUnavailable(f"MNI respondeu HTTP {response.status_code}")
        if response.status_code >= 400:
            raise AccessDenied(f"MNI recusou a chamada: HTTP {response.status_code}")
        return response.content

    def _call(
        self, numero: str, *, incluir_documentos: bool, ids: list[str] | None = None
    ) -> etree._Element:
        documentos = "".join(
            f"<ser:documento>{escape(doc_id)}</ser:documento>" for doc_id in (ids or [])
        )
        body = _ENVELOPE.format(
            id_consultante=escape(self._id),
            senha=escape(self._senha),
            numero=_sanitize_numero(numero),
            incluir_documentos="true" if incluir_documentos else "false",
            documentos=documentos,
        )
        raw = self._post(body)
        try:
            root = etree.fromstring(raw)
        except etree.XMLSyntaxError as exc:
            raise LayoutUnknown("resposta MNI nao e XML valido") from exc
        faults = root.xpath("//*[local-name()='Fault']")
        if faults:
            code = faults[0].findtext("faultcode") or "soap-fault"
            raise LayoutUnknown(f"SOAP Fault do MNI: {code[:80]}")
        self._check_sucesso(root)
        return root

    def _check_sucesso(self, root: etree._Element) -> None:
        sucesso = root.xpath("//*[local-name()='sucesso']/text()")
        mensagem = (root.xpath("//*[local-name()='mensagem']/text()") or [""])[0]
        if sucesso and sucesso[0].strip().lower() != "true":
            safe = mensagem[:200]
            if any(hint in safe.casefold() for hint in _AUTH_HINTS):
                raise AccessDenied(f"MNI negou a consulta: {safe}")
            raise LayoutUnknown(f"MNI sem sucesso: {safe}")

    # -- operações --------------------------------------------------------

    def consultar_processo(self, numero: str) -> MniConsultaResult:
        root = self._call(numero, incluir_documentos=True)
        mensagem = (root.xpath("//*[local-name()='mensagem']/text()") or [""])[0]
        documentos: list[MniDocumentoMeta] = []
        conteudo_inline = False
        for node in root.xpath("//*[local-name()='documento']"):
            meta = self._parse_documento(node, parent_id=None)
            documentos.append(meta)
            if node.xpath("./*[local-name()='conteudo']"):
                conteudo_inline = True
            for vinculado in node.xpath("./*[local-name()='documentoVinculado']"):
                documentos.append(self._parse_documento(vinculado, parent_id=meta.id))
        return MniConsultaResult(
            sucesso=True,
            mensagem=mensagem[:200],
            documentos=tuple(documentos),
            conteudo_inline=conteudo_inline,
        )

    def baixar_documentos(self, numero: str, ids: list[str]) -> dict[str, bytes]:
        root = self._call(numero, incluir_documentos=True, ids=list(ids))
        blobs: dict[str, bytes] = {}
        for node in root.xpath("//*[local-name()='documento']"):
            doc_id = node.get("idDocumento")
            conteudo = node.xpath("./*[local-name()='conteudo']/text()")
            if doc_id in ids and conteudo:
                try:
                    blobs[doc_id] = base64.b64decode("".join(conteudo), validate=True)
                except Exception as exc:  # noqa: BLE001 - base64 invalido e falha de download
                    raise DocumentDownloadFailed(f"base64 invalido para {doc_id}") from exc
        missing = [doc_id for doc_id in ids if doc_id not in blobs]
        if missing:
            raise DocumentDownloadFailed(f"MNI nao devolveu teor de: {', '.join(missing[:5])}")
        return blobs

    @staticmethod
    def _parse_documento(node: etree._Element, *, parent_id: str | None) -> MniDocumentoMeta:
        doc_id = node.get("idDocumento")
        if not doc_id:
            raise LayoutUnknown("documento MNI sem idDocumento")
        try:
            nivel = int(node.get("nivelSigilo") or 0)
        except ValueError:
            nivel = 0
        return MniDocumentoMeta(
            id=doc_id,
            tipo=node.get("tipoDocumento"),
            descricao=node.get("descricao"),
            data_hora=node.get("dataHora"),
            mimetype=node.get("mimetype"),
            nivel_sigilo=nivel,
            parent_id=parent_id,
        )
