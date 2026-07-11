"""Harness de validação live: redação do número e formato do resultado."""

from datetime import datetime, timezone

from app.connectors.live_validation import (
    LiveValidationResult,
    redact_process_number,
    result_to_public_dict,
)


def test_process_number_is_redacted_to_last_four_digits():
    assert redact_process_number("0000001-00.2024.8.26.0100") == "****0100"
    assert redact_process_number("12345") == "****2345"
    assert redact_process_number("7") == "****7"


def test_result_public_dict_omits_evidence_payload():
    result = LiveValidationResult(
        profile_key="pje:tjmg:1",
        capability="read_autos",
        passed=True,
        manifest_fingerprint="sha256:abc",
        documents_count=3,
        error_code=None,
        evidence_keys=("trace", "screenshot"),
        tested_at=datetime(2026, 7, 10, tzinfo=timezone.utc),
    )
    public = result_to_public_dict(result)
    assert public["profile_key"] == "pje:tjmg:1"
    assert public["documents_count"] == 3
    assert public["evidence_keys"] == ["trace", "screenshot"]
    # nunca expõe conteúdo/DOM, só as chaves da evidência
    assert "evidence" not in public
    assert "dom" not in public
