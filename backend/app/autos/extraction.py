"""Extração de texto por página, com OCR só onde não há camada textual.

Página sem texto nativo e sem OCR útil é falha explícita — nunca uma página
silenciosamente vazia dentro do contexto.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

import fitz
from PIL import Image

from app.settings import settings


class PdfExtractionError(RuntimeError):
    def __init__(self, message: str, *, diagnostics: list | None = None):
        super().__init__(message)
        self.diagnostics = diagnostics or []


@dataclass(frozen=True)
class ExtractedPage:
    page: int
    text: str
    ocr: bool


@dataclass(frozen=True)
class ExtractionResult:
    page_count: int
    pages: tuple[ExtractedPage, ...]
    text_sha256: str


def _ocr_image(image: Image.Image) -> str:
    import pytesseract

    if settings.tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd
    return pytesseract.image_to_string(image, lang=settings.tesseract_language)


def extract_pdf_pages(pdf_bytes: bytes, *, cached_pages: list | None = None) -> ExtractionResult:
    pages: list[ExtractedPage] = []
    diagnostics = []
    cached = {p["page"]: p for p in cached_pages or [] if p.get("status") == "complete" and p.get("text")}
    try:
        document = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as exc:  # noqa: BLE001 - MuPDF levanta tipos variados
        raise PdfExtractionError(f"invalid PDF: {exc}") from exc
    with document:
        for index, page in enumerate(document, start=1):
            if index in cached:
                item = cached[index]
                diagnostics.append(item)
                pages.append(ExtractedPage(page=index, text=item["text"], ocr=item["ocr"]))
                continue
            used_ocr = False
            try:
                text = page.get_text("text").strip()
                if len(text) < settings.ocr_min_text_chars:
                    used_ocr = True
                    pix = page.get_pixmap(dpi=settings.ocr_dpi, alpha=False)
                    image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                    text = _ocr_image(image).strip()
                if not text:
                    raise PdfExtractionError("Página sem texto legível; conferir imagem ou página em branco")
            except Exception:
                diagnostics.append({"page": index, "status": "failed", "ocr": used_ocr,
                    "error": "Não foi possível extrair texto. Confira a página original e reprocese."})
                continue
            diagnostics.append({"page": index, "status": "complete", "text": text, "ocr": used_ocr, "chars": len(text)})
            pages.append(ExtractedPage(page=index, text=text, ocr=used_ocr))

    failed = [p["page"] for p in diagnostics if p["status"] == "failed"]
    if failed:
        raise PdfExtractionError(f"Falha de extração nas páginas: {', '.join(map(str, failed[:100]))}", diagnostics=diagnostics)

    full_text = "\n".join(page.text for page in pages)
    return ExtractionResult(
        page_count=len(pages),
        pages=tuple(pages),
        text_sha256=sha256(full_text.encode("utf-8")).hexdigest(),
    )
