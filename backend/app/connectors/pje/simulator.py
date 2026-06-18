"""Local fake PJe page for connector development without tribunal access."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


FAKE_PROCESSO = "0000001-00.2024.8.26.0100"


SIMULATOR_HTML = f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <title>PJe Simulator - Causor</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 32px; color: #1f2937; }}
    main {{ max-width: 900px; margin: 0 auto; }}
    label, select, input, button {{ display: block; margin: 12px 0; }}
    input, select {{ padding: 8px; width: 360px; }}
    button, a[role="button"] {{ padding: 8px 12px; cursor: pointer; }}
    .box {{ border: 1px solid #cbd5e1; padding: 16px; margin-top: 16px; }}
    .muted {{ color: #64748b; }}
  </style>
</head>
<body>
  <main>
    <h1>Painel do Advogado - PJe Simulator</h1>
    <p class="muted">Ambiente falso para testar o conector Causor. Nao use como PJe real.</p>
    <section id="search" class="box">
      <h2>Processo &gt; Pesquisar &gt; Processo</h2>
      <label for="numeroProcesso">Numero do processo</label>
      <input id="numeroProcesso" name="numeroProcesso" placeholder="Numero do processo">
      <button type="button" id="pesquisar">Pesquisar</button>
      <div id="resultado"></div>
    </section>
    <section id="autos" class="box" hidden></section>
  </main>
  <script>
    const formattedNumber = "{FAKE_PROCESSO}";
    const digits = formattedNumber.replace(/\\D/g, "");

    document.getElementById("pesquisar").addEventListener("click", () => {{
      const informed = document.getElementById("numeroProcesso").value.replace(/\\D/g, "");
      const result = document.getElementById("resultado");
      result.innerHTML = `<p>Consulta de processos</p>
        <a href="#autos" id="abrirProcesso">${{formattedNumber}}</a>`;
      document.getElementById("abrirProcesso").addEventListener("click", event => {{
        event.preventDefault();
        showAutos();
      }});
    }});

    function showAutos() {{
      document.getElementById("autos").hidden = false;
      document.getElementById("autos").innerHTML = `
        <h2>Autos digitais - ${{formattedNumber}}</h2>
        <p>Processo localizado. Use a aba para juntar documentos.</p>
        <button type="button" id="juntar">Anexar Peticoes/Documentos</button>`;
      document.getElementById("juntar").addEventListener("click", showPeticionar);
    }}

    function showPeticionar() {{
      document.getElementById("autos").innerHTML = `
        <h2>Juntar documentos</h2>
        <label for="tipoPeticao">Tipo da peticao</label>
        <select id="tipoPeticao" name="tipoPeticao">
          <option>Manifestacao</option>
          <option>Peticao intermediaria</option>
        </select>
        <label for="arquivoPeticao">Arquivo PDF</label>
        <input id="arquivoPeticao" type="file" accept="application/pdf">
        <div id="assinatura"></div>`;
      document.getElementById("arquivoPeticao").addEventListener("change", () => {{
        document.getElementById("assinatura").innerHTML = `
          <p>Documento anexado. PJeOffice disponivel.</p>
          <button type="button">Assinar documento</button>
          <button type="button">Protocolar</button>`;
      }});
    }}
  </script>
</body>
</html>
"""


class PjeSimulatorHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - stdlib API
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(SIMULATOR_HTML.encode("utf-8"))

    def log_message(self, format: str, *args) -> None:  # noqa: A002 - stdlib API
        return


def build_server(host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), PjeSimulatorHandler)


def serve(host: str = "127.0.0.1", port: int = 8765) -> None:
    server = build_server(host, port)
    print(f"PJe simulator em http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
