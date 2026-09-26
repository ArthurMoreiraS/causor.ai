from pathlib import Path

import pytest

from app.autos.extraction import PdfExtractionError, extract_pdf_pages

FIXTURES = Path(__file__).parent / "fixtures" / "pdfs"


@pytest.fixture
def textual_pdf_bytes():
    return (FIXTURES / "textual.pdf").read_bytes()


@pytest.fixture
def scanned_pdf_bytes():
    return (FIXTURES / "scanned.pdf").read_bytes()


def test_extracts_text_with_page_numbers(textual_pdf_bytes):
    result = extract_pdf_pages(textual_pdf_bytes)
    assert result.page_count == 2
    assert result.pages[0].page == 1
    assert "CONTRATO" in result.pages[0].text
    assert result.pages[0].ocr is False


def test_uses_ocr_only_for_page_without_text(scanned_pdf_bytes, monkeypatch):
    monkeypatch.setattr("app.autos.extraction._ocr_image", lambda image: "TEXTO OCR")
    result = extract_pdf_pages(scanned_pdf_bytes)
    assert result.pages[0].text == "TEXTO OCR"
    assert result.pages[0].ocr is True


def test_page_without_any_text_is_an_explicit_failure(scanned_pdf_bytes, monkeypatch):
    monkeypatch.setattr("app.autos.extraction._ocr_image", lambda image: "")
    with pytest.raises(PdfExtractionError):
        extract_pdf_pages(scanned_pdf_bytes)


def test_text_sha256_is_deterministic(textual_pdf_bytes):
    first = extract_pdf_pages(textual_pdf_bytes)
    second = extract_pdf_pages(textual_pdf_bytes)
    assert first.text_sha256 == second.text_sha256


def test_partial_failure_preserves_good_pages_and_retries_only_failed_page(monkeypatch):
    import fitz
    with fitz.open() as doc:
        doc.new_page()
        doc.new_page()
        data = doc.tobytes()
    responses = iter(["Texto OCR da primeira página", ""])
    monkeypatch.setattr("app.autos.extraction._ocr_image", lambda image: next(responses))
    with pytest.raises(PdfExtractionError) as failure:
        extract_pdf_pages(data)
    cache = failure.value.diagnostics
    assert [p["status"] for p in cache] == ["complete", "failed"]
    calls = []
    monkeypatch.setattr("app.autos.extraction._ocr_image", lambda image: calls.append(True) or "Texto recuperado da segunda página")
    result = extract_pdf_pages(data, cached_pages=cache)
    assert len(calls) == 1
    assert result.page_count == 2
    assert result.pages[0].text == "Texto OCR da primeira página"
    assert result.pages[1].page == 2
