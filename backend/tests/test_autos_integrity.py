import pytest

from app.autos.contracts import ManifestDocumentInput, ManifestInput
from app.autos.integrity import (
    InvalidPdfError,
    completeness_result,
    fingerprint_manifest,
    validate_pdf,
)


def _manifest(order=("a", "b"), cursor_complete=True):
    return ManifestInput(
        cursor_complete=cursor_complete,
        documents=[
            ManifestDocumentInput(
                external_id=value,
                nome=f"{value}.pdf",
                tipo=None,
                ordem=index,
                parent_external_id=None,
                data_documento=None,
                sigiloso=False,
                mime_type="application/pdf",
                size_hint=None,
                download_ref=f"opaque:{value}",
            )
            for index, value in enumerate(order, start=1)
        ],
        evidence={},
    )


def test_manifest_fingerprint_is_ordered_and_deterministic():
    assert fingerprint_manifest(_manifest()) == fingerprint_manifest(_manifest())
    assert fingerprint_manifest(_manifest()) != fingerprint_manifest(_manifest(("b", "a")))


def test_html_login_page_is_not_accepted_as_pdf():
    with pytest.raises(InvalidPdfError):
        validate_pdf(b"<html>login</html>", declared_mime="application/pdf")


def test_valid_pdf_passes_validation():
    validate_pdf(b"%PDF-1.4\ncontent\n%%EOF\n", declared_mime="application/pdf")


def test_unexpected_mime_is_rejected():
    with pytest.raises(InvalidPdfError):
        validate_pdf(b"%PDF-1.4\ncontent\n%%EOF\n", declared_mime="text/html")


def test_completeness_requires_identical_manifests_and_verified_items():
    initial = _manifest(("a", "b"))
    final = _manifest(("a", "b"))

    complete = completeness_result(initial, final, {"a": "verified", "b": "verified"})
    assert complete.complete is True
    assert complete.missing == []
    assert complete.extra == []
    assert complete.failed == []

    changed = completeness_result(_manifest(("a",)), final, {"a": "verified"})
    assert changed.complete is False
    assert changed.extra == ["b"]

    failed = completeness_result(initial, final, {"a": "verified", "b": "failed"})
    assert failed.complete is False
    assert failed.failed == ["b"]

    partial_cursor = completeness_result(
        _manifest(("a", "b"), cursor_complete=False), final, {"a": "verified", "b": "verified"}
    )
    assert partial_cursor.complete is False
