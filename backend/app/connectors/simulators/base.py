"""Base de simulador sanitizado de portal judicial.

Serve páginas sintéticas para desenvolver e testar os conectores sem acesso a
tribunal real. Nada aqui contém número real, partes, teor, cookie ou token: os
documentos são fixos ``SIM-DOC-001..003`` (um anexo aninhado, um sigiloso) e os
PDFs são bytes mínimos válidos.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SIM_PROCESSO = "0000000-00.2026.8.00.0000"


def fake_pdf(marker: str) -> bytes:
    return b"%PDF-1.4\n%" + marker.encode("ascii", "ignore") + b"\n%%EOF\n"


@dataclass(frozen=True)
class SimulatorDocument:
    external_id: str
    nome: str
    tipo: str
    page: int
    sigiloso: bool = False
    parent_external_id: str | None = None
    pdf_bytes: bytes = b"%PDF-1.4\n%%EOF\n"


def _default_documents() -> list[SimulatorDocument]:
    return [
        SimulatorDocument(
            external_id="SIM-DOC-001",
            nome="Peticao inicial.pdf",
            tipo="Petição inicial",
            page=1,
            pdf_bytes=fake_pdf("SIM-DOC-001"),
        ),
        SimulatorDocument(
            external_id="SIM-DOC-002",
            nome="Decisao.pdf",
            tipo="Decisão",
            page=2,
            pdf_bytes=fake_pdf("SIM-DOC-002"),
        ),
        SimulatorDocument(
            external_id="SIM-DOC-003",
            nome="Anexo sigiloso.pdf",
            tipo="Anexo",
            page=2,
            sigiloso=True,
            parent_external_id="SIM-DOC-002",
            pdf_bytes=fake_pdf("SIM-DOC-003"),
        ),
    ]


@dataclass
class CourtSimulator:
    """Provedor de páginas sintéticas de uma família de sistema.

    Subclasses ajustam rótulos/marcadores por família; o conjunto de
    documentos e a mecânica de páginas são comuns.
    """

    sistema: str
    login_marker: str = "Certificado digital"
    panel_marker: str = "Painel do Advogado"
    secret_label: str = "Documento restrito"
    documents: list[SimulatorDocument] = field(default_factory=_default_documents)

    def login_html(self) -> str:
        """Tela de login com as duas armadilhas reais dos portais.

        Tem formulário de senha de verdade (o que a detecção por seletor usa)
        e a palavra "processo" no texto — que era marcador de *autenticado* em
        ``pje/pages/login.py`` e fazia sessão morta passar por válida.
        """
        return (
            f"<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'>"
            f"<title>{self.sistema} Simulator</title></head><body>"
            f"<h1>Acesso {self.sistema}</h1>"
            f"<p>Consulta e peticionamento de processo eletronico.</p>"
            f"<form id='form-login' method='post'>"
            f"<input type='text' name='usuario' placeholder='Usuario'>"
            f'<input type="password" name="senha" placeholder="Senha">'
            f"<button type='submit'>Entrar</button>"
            f"</form>"
            f"<button type='button'>{self.login_marker}</button>"
            f"<button type='button'>Entrar com gov.br</button>"
            f"</body></html>"
        )

    def panel_html(self) -> str:
        """Painel autenticado com "Alterar Senha" no menu.

        Essa é a armadilha que fazia ``handlers.py`` nunca confirmar o login:
        a substring "senha" aparece, mas não existe formulário de senha.
        """
        return (
            f"<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'>"
            f"<title>{self.sistema} Simulator</title></head><body>"
            f"<header>{self.panel_marker}"
            f" · <a href='#alterar-senha'>Alterar Senha</a>"
            f' · <a href="#logout">Sair</a></header>'
            f"<section id='autos'>{self.autos_html(page=1)}</section>"
            f"</body></html>"
        )

    def autos_html(self, *, page: int) -> str:
        rows = []
        for doc in self.documents:
            if doc.page != page:
                continue
            label = f" <em>{self.secret_label}</em>" if doc.sigiloso else ""
            parent = (
                f" data-parent='{doc.parent_external_id}'" if doc.parent_external_id else ""
            )
            rows.append(
                f"<li data-doc-id='{doc.external_id}'{parent}>"
                f"<a href='/download?doc={doc.external_id}'>{doc.nome}</a>{label}</li>"
            )
        terminator = (
            "<span data-cursor='end'>fim da lista</span>"
            if page >= self._last_page()
            else "<a href='/autos?page=%d' data-cursor='next'>proxima</a>" % (page + 1)
        )
        return f"<ul class='autos'>{''.join(rows)}</ul>{terminator}"

    def filing_html(self) -> str:
        return (
            "<form id='peticionar'>"
            "<select name='tipo'><option>Manifestacao</option></select>"
            "<input type='file' name='arquivo' accept='application/pdf'>"
            "<button type='button' id='assinar'>Assinar documento</button>"
            "</form>"
        )

    def receipt_html(self, *, protocolo: str) -> str:
        return (
            "<section id='comprovante'>"
            f"<p>Protocolo registrado: <strong data-protocolo>{protocolo}</strong></p>"
            "<a href='/download?doc=comprovante'>Comprovante (PDF)</a>"
            "</section>"
        )

    def download(self, external_id: str) -> bytes:
        for doc in self.documents:
            if doc.external_id == external_id:
                return doc.pdf_bytes
        return fake_pdf("comprovante")

    def _last_page(self) -> int:
        return max((doc.page for doc in self.documents), default=1)


def build_handler(simulator: CourtSimulator) -> type[BaseHTTPRequestHandler]:
    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - stdlib API
            if self.path.startswith("/download"):
                self.send_response(200)
                self.send_header("Content-Type", "application/pdf")
                self.end_headers()
                self.wfile.write(fake_pdf("download"))
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(simulator.panel_html().encode("utf-8"))

        def log_message(self, format: str, *args) -> None:  # noqa: A002 - stdlib API
            return

    return _Handler


def build_server(
    simulator: CourtSimulator, host: str = "127.0.0.1", port: int = 0
) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), build_handler(simulator))
