"""Render petition drafts into PDF bytes for court filing."""

from __future__ import annotations

import io
from datetime import datetime, timezone
from pathlib import Path

from fpdf import FPDF
from fpdf.enums import XPos, YPos
from PIL import Image

from app.filing.timbrado import TimbradoEscritorio

_FONT_DIR = Path(__file__).parent / "fonts"
_PAGE_WIDTH_MM = 210.0


class _MinutaPDF(FPDF):
    """A4 com cabeçalho/rodapé repetidos por página quando há timbrado."""

    def __init__(self, timbrado: TimbradoEscritorio | None) -> None:
        super().__init__(orientation="P", unit="mm", format="A4")
        self.timbrado = timbrado
        self.add_font("DejaVu", "", str(_FONT_DIR / "DejaVuSans.ttf"))
        self.add_font("DejaVu", "B", str(_FONT_DIR / "DejaVuSans-Bold.ttf"))
        self.set_auto_page_break(auto=True, margin=30)

    def header(self) -> None:
        t = self.timbrado
        if t is None:
            return
        y = 10.0
        if t.logo:
            # Centraliza o logo com 14mm de altura preservando a proporção.
            with Image.open(io.BytesIO(t.logo)) as img:
                largura_mm = min(14.0 * img.width / img.height, 60.0)
            self.image(io.BytesIO(t.logo), x=(_PAGE_WIDTH_MM - largura_mm) / 2, y=y, h=14.0)
            y += 16.0
        self.set_y(y)
        self.set_font("DejaVu", "B", 11)
        self.cell(0, 5.5, t.nome, align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        if t.cabecalho:
            self.set_font("DejaVu", "", 8)
            self.set_text_color(90)
            for linha in t.cabecalho.splitlines():
                self.cell(0, 4, linha, align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            self.set_text_color(0)
        self.ln(2)
        self.set_draw_color(170)
        self.line(self.l_margin, self.get_y(), _PAGE_WIDTH_MM - self.r_margin, self.get_y())
        self.ln(6)

    def footer(self) -> None:
        self.set_y(-24)
        self.set_font("DejaVu", "", 7.5)
        self.set_text_color(120)
        t = self.timbrado
        if t is not None:
            self.set_draw_color(170)
            self.line(self.l_margin, self.get_y(), _PAGE_WIDTH_MM - self.r_margin, self.get_y())
            self.ln(2)
            if t.rodape:
                for linha in t.rodape.splitlines():
                    self.cell(0, 3.8, linha, align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.cell(0, 3.8, f"página {self.page_no()} de {{nb}}", align="R")
        self.set_text_color(0)


def render_minuta_pdf(
    texto: str,
    *,
    meta: dict | None = None,
    timbrado: TimbradoEscritorio | None = None,
) -> bytes:
    """PDF da minuta: neutro sem timbrado; com timbrado, identidade do
    escritório em toda página. Função pura — o timbrado chega pronto de
    load_timbrado, sem acesso a banco aqui."""

    meta = meta or {}
    pdf = _MinutaPDF(timbrado)
    pdf.alias_nb_pages()
    pdf.add_page()

    pdf.set_font("DejaVu", "", 9)
    pdf.set_text_color(90)
    if timbrado is None:
        pdf.set_font("DejaVu", "B", 11)
        pdf.set_text_color(0)
        pdf.cell(0, 6, "Causor - Minuta para protocolo", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("DejaVu", "", 9)
        pdf.set_text_color(90)
        gerado = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        pdf.cell(0, 5, f"Gerado em: {gerado}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    for rotulo, chave in (("Processo", "processo"), ("Tipo", "tipo"), ("Tribunal", "tribunal")):
        if meta.get(chave):
            pdf.cell(0, 5, f"{rotulo}: {meta[chave]}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(0)
    pdf.ln(4)

    pdf.set_font("DejaVu", "", 10.5)
    pdf.multi_cell(0, 5.5, texto or "", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    return bytes(pdf.output())
