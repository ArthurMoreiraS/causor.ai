"""Tests for rendering petition drafts into a filing PDF."""

import io
import re

from PIL import Image
from pypdf import PdfReader

from app.filing.render import render_minuta_pdf
from app.filing.timbrado import TimbradoEscritorio


def _texto_do_pdf(pdf: bytes) -> str:
    reader = PdfReader(io.BytesIO(pdf))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _png_bytes(largura: int = 60, altura: int = 20) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (largura, altura), "red").save(buf, format="PNG")
    return buf.getvalue()


def _timbrado(**overrides) -> TimbradoEscritorio:
    base = dict(
        nome="Moura & Santos Advogados",
        cabecalho="Av. Paulista, 1000 - São Paulo/SP\ncontato@moura.adv.br",
        rodape="OAB/SP 123.456 · moura.adv.br",
        logo=_png_bytes(),
        logo_mime="image/png",
    )
    base.update(overrides)
    return TimbradoEscritorio(**base)


def test_render_sem_timbrado_mantem_formato_neutro():
    pdf = render_minuta_pdf(
        "Excelentissimo Juizo\n\nRequer a juntada da manifestacao.",
        meta={"processo": "0000001-00.2024.8.26.0100", "tipo": "Manifestacao"},
    )

    assert pdf.startswith(b"%PDF")
    texto = _texto_do_pdf(pdf)
    assert "Causor - Minuta para protocolo" in texto
    assert "Excelentissimo Juizo" in texto
    assert "0000001-00.2024.8.26.0100" in texto


def test_render_com_timbrado_estampa_cabecalho_e_rodape():
    pdf = render_minuta_pdf("Corpo da peça.", meta={"processo": "123"}, timbrado=_timbrado())

    texto = _texto_do_pdf(pdf)
    assert "Moura & Santos Advogados" in texto
    assert "Av. Paulista, 1000 - São Paulo/SP" in texto
    assert "OAB/SP 123.456 · moura.adv.br" in texto
    assert "Corpo da peça." in texto
    assert "página 1 de 1" in texto
    assert "Causor - Minuta para protocolo" not in texto


def test_render_multipagina_repete_timbrado_em_toda_pagina():
    corpo = "\n".join(f"Parágrafo {i} da fundamentação." for i in range(200))
    pdf = render_minuta_pdf(corpo, timbrado=_timbrado())

    reader = PdfReader(io.BytesIO(pdf))
    assert len(reader.pages) >= 2
    ultima = reader.pages[-1].extract_text() or ""
    assert "Moura & Santos Advogados" in ultima
    assert f"página {len(reader.pages)} de {len(reader.pages)}" in ultima


def test_render_aceita_caracteres_fora_do_latin1():
    pdf = render_minuta_pdf("Cita-se o “precedente” — grifo nosso.", timbrado=_timbrado())

    texto = _texto_do_pdf(pdf)
    assert "“precedente”" in texto
    assert "—" in texto


def test_render_timbrado_sem_logo_nao_quebra():
    pdf = render_minuta_pdf("Texto.", timbrado=_timbrado(logo=None, logo_mime=None))

    assert pdf.startswith(b"%PDF")
    assert "Moura & Santos Advogados" in _texto_do_pdf(pdf)


def test_render_logo_largo_respeita_cap_de_60mm():
    pdf = render_minuta_pdf("Texto.", timbrado=_timbrado(logo=_png_bytes(largura=500, altura=50)))

    reader = PdfReader(io.BytesIO(pdf))
    conteudo = reader.pages[0].get_contents().get_data().decode("latin-1")
    matrizes = re.findall(r"([\d.]+) 0 0 ([\d.]+) [\d.]+ [\d.]+ cm", conteudo)
    assert matrizes, "nenhuma imagem encontrada no content stream"
    largura_pt = max(float(m[0]) for m in matrizes)
    assert largura_pt <= 60 / 25.4 * 72 + 0.5


def test_render_timbrado_com_cabecalho_e_rodape_longos_nao_estoura_pagina():
    """Cabeçalho/rodapé com muitas linhas antes causavam RecursionError
    (header -> add_page -> header ...) ou empurravam o rodapé para fora
    da página. O renderer deve truncar e continuar produzindo um PDF válido
    com o rodapé (e o número de página) visível na página 1."""
    cabecalho_longo = "\n".join(f"Linha de cabeçalho {i}" for i in range(100))
    rodape_longo = "\n".join(f"Linha de rodapé {i}" for i in range(30))
    pdf = render_minuta_pdf(
        "Corpo da peça.",
        timbrado=_timbrado(cabecalho=cabecalho_longo, rodape=rodape_longo),
    )

    assert pdf.startswith(b"%PDF")
    reader = PdfReader(io.BytesIO(pdf))
    texto_pagina_1 = reader.pages[0].extract_text() or ""
    assert "página 1 de" in texto_pagina_1
