"""Render petition drafts into simple PDF bytes for court filing."""

from __future__ import annotations

from datetime import datetime, timezone
import textwrap


def _pdf_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _lines(text: str, *, width: int = 92) -> list[str]:
    rendered: list[str] = []
    for raw_line in (text or "").splitlines() or [""]:
        if raw_line.strip() == "":
            rendered.append("")
            continue
        rendered.extend(textwrap.wrap(raw_line, width=width) or [""])
    return rendered


def render_minuta_pdf(texto: str, *, meta: dict | None = None) -> bytes:
    """Return a minimal, deterministic PDF for a plain-text petition draft.

    The MVP filing package only needs readable text. Keeping this renderer pure
    avoids adding a browser/PDF service to the critical path before the PJe
    connector has real homologation fixtures.
    """

    meta = meta or {}
    header = [
        "Causor - Minuta para protocolo",
        f"Gerado em: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
    ]
    if meta.get("processo"):
        header.append(f"Processo: {meta['processo']}")
    if meta.get("tipo"):
        header.append(f"Tipo: {meta['tipo']}")
    if meta.get("tribunal"):
        header.append(f"Tribunal: {meta['tribunal']}")

    body_lines = header + [""] + _lines(texto or "")
    stream_parts = ["BT", "/F1 10 Tf", "50 792 Td", "14 TL"]
    for index, line in enumerate(body_lines):
        if index:
            stream_parts.append("T*")
        stream_parts.append(f"({_pdf_escape(line)}) Tj")
    stream_parts.append("ET")
    stream = "\n".join(stream_parts).encode("latin-1", errors="replace")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 842] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
    ]

    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{number} 0 obj\n".encode("ascii"))
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")

    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("ascii")
    )
    return bytes(pdf)
