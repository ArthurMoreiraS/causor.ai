"""Simulador SOAP do MNI, sanitizado como os demais simuladores.

Serve ``consultarProcesso`` com os documentos SIM-DOC-001..003 (um vinculado
e sigiloso); senha errada devolve ``sucesso=false`` com mensagem de
autorização. Nada aqui contém dado real.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from app.connectors.simulators.base import SimulatorDocument, _default_documents


def _doc_xml(doc: SimulatorDocument, *, include_content: bool, requested: set[str]) -> str:
    conteudo = ""
    if include_content and (not requested or doc.external_id in requested):
        payload = base64.b64encode(doc.pdf_bytes).decode("ascii")
        conteudo = f"<conteudo>{payload}</conteudo>"
    attrs = (
        f'idDocumento="{doc.external_id}" tipoDocumento="1" '
        f'dataHora="20260701120000" mimetype="application/pdf" '
        f'nivelSigilo="{1 if doc.sigiloso else 0}" descricao="{doc.nome}"'
    )
    return f"<documento {attrs}>{conteudo}</documento>"


@dataclass
class MniSimulator:
    senha_valida: str = "sim-senha"
    documents: list[SimulatorDocument] = field(default_factory=_default_documents)

    def responder(self, body: str) -> str:
        senha_ok = f"<ser:senhaConsultante>{self.senha_valida}</ser:senhaConsultante>" in body
        if not senha_ok:
            return self._envelope(
                "<sucesso>false</sucesso><mensagem>Usuario ou senha invalidos</mensagem>"
            )
        requested = {
            doc.external_id
            for doc in self.documents
            if f">{doc.external_id}</ser:documento>" in body
        }
        include_content = bool(requested)
        docs = "".join(
            _doc_xml(doc, include_content=include_content, requested=requested)
            for doc in self.documents
        )
        return self._envelope(
            "<sucesso>true</sucesso><mensagem>ok</mensagem>"
            "<processo><dadosBasicos numero='00000000020268130000' nivelSigilo='0'/>"
            f"{docs}</processo>"
        )

    @staticmethod
    def _envelope(inner: str) -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" '
            'xmlns:ns2="http://www.cnj.jus.br/intercomunicacao-2.2.2">'
            f"<soap:Body><ns2:consultarProcessoResposta>{inner}"
            "</ns2:consultarProcessoResposta></soap:Body></soap:Envelope>"
        )


def build_mni_server(
    simulator: MniSimulator, host: str = "127.0.0.1", port: int = 0
) -> ThreadingHTTPServer:
    class _Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802 - stdlib API
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8")
            response = simulator.responder(body).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/xml; charset=utf-8")
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)

        def log_message(self, format: str, *args) -> None:  # noqa: A002 - stdlib API
            return

    return ThreadingHTTPServer((host, port), _Handler)
