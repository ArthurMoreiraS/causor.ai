"""Tests for rendering petition drafts into a filing PDF."""

from app.filing.render import render_minuta_pdf


def test_render_minuta_pdf_returns_valid_pdf_bytes():
    pdf = render_minuta_pdf(
        "Excelentissimo Juizo\n\nRequer a juntada da manifestacao.",
        meta={"processo": "0000001-00.2024.8.26.0100", "tipo": "Manifestacao"},
    )

    assert pdf.startswith(b"%PDF")
    assert b"%%EOF" in pdf
    assert b"Excelentissimo Juizo" in pdf
    assert b"0000001-00.2024.8.26.0100" in pdf
