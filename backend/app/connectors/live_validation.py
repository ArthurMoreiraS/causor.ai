"""Harness de validação live read-only dos conectores.

Roda só na máquina autorizada do advogado (via agente local); a CI sempre
pula. O resultado é enviado ao backend pela API autenticada; número do
processo é redigido e trace/DOM nunca entram no repositório.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class LiveValidationResult:
    profile_key: str
    capability: str
    passed: bool
    manifest_fingerprint: str | None
    documents_count: int | None
    error_code: str | None
    evidence_keys: tuple[str, ...]
    tested_at: datetime


def redact_process_number(numero: str) -> str:
    """Mantém apenas os quatro últimos dígitos; o resto vira ``****``."""
    digits = "".join(ch for ch in numero if ch.isdigit())
    return "****" + digits[-4:]


def result_to_public_dict(result: LiveValidationResult) -> dict:
    """Serializa o resultado sem expor evidência/DOM — só as chaves."""
    return {
        "profile_key": result.profile_key,
        "capability": result.capability,
        "passed": result.passed,
        "manifest_fingerprint": result.manifest_fingerprint,
        "documents_count": result.documents_count,
        "error_code": result.error_code,
        "evidence_keys": list(result.evidence_keys),
        "tested_at": result.tested_at.isoformat(),
    }
