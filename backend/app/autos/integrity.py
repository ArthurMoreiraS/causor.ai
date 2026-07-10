"""Fingerprint canônico, validação de PDF e prova de completude.

`cursor_complete=False` nunca resulta em captura completa; enumeração inicial
e final precisam ser idênticas e todo item precisa estar `verified`.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json

from app.autos.contracts import ManifestInput


class InvalidPdfError(ValueError):
    pass


def fingerprint_manifest(manifest: ManifestInput) -> str:
    """SHA-256 canônico da enumeração: apenas campos estáveis, em ordem."""
    payload = [
        {
            "external_id": doc.external_id,
            "nome": doc.nome,
            "tipo": doc.tipo,
            "ordem": doc.ordem,
            "parent_external_id": doc.parent_external_id,
            "data_documento": doc.data_documento.isoformat() if doc.data_documento else None,
            "sigiloso": doc.sigiloso,
        }
        for doc in manifest.documents
    ]
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return f"sha256:{sha256(canonical.encode('utf-8')).hexdigest()}"


def validate_pdf(data: bytes, *, declared_mime: str | None) -> None:
    if not data.startswith(b"%PDF-"):
        raise InvalidPdfError("download is not a PDF")
    if b"%%EOF" not in data[-4096:]:
        raise InvalidPdfError("PDF has no EOF marker")
    if declared_mime not in {None, "application/pdf", "application/octet-stream"}:
        raise InvalidPdfError(f"unexpected MIME type: {declared_mime}")


@dataclass(frozen=True)
class CompletenessResult:
    complete: bool
    missing: list[str]
    extra: list[str]
    failed: list[str]


def completeness_result(
    initial: ManifestInput,
    final: ManifestInput,
    item_statuses: dict[str, str],
) -> CompletenessResult:
    """Prova binária de completude da captura, com listas exatas para auditoria.

    ``missing``: IDs previstos no inicial que sumiram do final;
    ``extra``: IDs que apareceram no final sem estar previstos no inicial;
    ``failed``: itens sem verificação de download. Qualquer lista não vazia
    (ou cursor incompleto, ou fingerprints distintos) quebra a completude.
    """
    initial_set = {doc.external_id for doc in initial.documents}
    final_set = {doc.external_id for doc in final.documents}

    missing = sorted(initial_set - final_set)
    extra = sorted(final_set - initial_set)
    failed = sorted(
        external_id
        for external_id in initial_set | final_set
        if item_statuses.get(external_id) != "verified"
    )

    complete = (
        initial.cursor_complete
        and final.cursor_complete
        and fingerprint_manifest(initial) == fingerprint_manifest(final)
        and not missing
        and not extra
        and not failed
    )
    return CompletenessResult(complete=complete, missing=missing, extra=extra, failed=failed)
