import pytest

from app.connectors.errors import (
    CaptchaRequired,
    ConnectorError,
    LayoutUnknown,
    ReceiptNotVerified,
    SessionExpired,
    SystemMigrated,
)
from app.connectors.profiles import ConnectorCapabilities, ConnectorProfile


def _capabilities(**overrides) -> ConnectorCapabilities:
    values = dict(
        read_autos=True,
        read_secret=False,
        prepare_filing=True,
        submit_filing=False,
        download_receipt=False,
    )
    values.update(overrides)
    return ConnectorCapabilities(**values)


def _profile(**overrides) -> ConnectorProfile:
    values = dict(
        key="pje:tjmg:1",
        sistema="PJe",
        tribunal="TJMG",
        grau="1",
        url_base="https://pje.tjmg.jus.br/pje",
        filing_url=None,
        version_marker="pje-2.x",
        status="experimental",
        capabilities=_capabilities(),
    )
    values.update(overrides)
    return ConnectorProfile(**values)


def test_profile_accepts_valid_degrees_and_statuses():
    assert _profile(grau="2").grau == "2"
    assert _profile(status="supported").status == "supported"


def test_profile_rejects_invalid_degree():
    with pytest.raises(ValueError):
        _profile(grau="3")


def test_profile_rejects_unknown_status():
    with pytest.raises(ValueError):
        _profile(status="beta")


def test_canonical_errors_carry_code_and_safe_detail():
    err = SessionExpired()
    assert err.code == "session_expired"
    assert err.retryable is True
    assert err.requires_human is True
    assert isinstance(err, ConnectorError)

    captcha = CaptchaRequired()
    assert captcha.code == "captcha_required"

    layout = LayoutUnknown(safe_detail="marcador v9 nao encontrado")
    assert layout.code == "layout_unknown"
    assert "marcador" in str(layout)

    receipt = ReceiptNotVerified()
    assert receipt.retryable is False


def test_canonical_error_str_never_leaks_urls_or_page_content():
    err = SessionExpired(safe_detail="painel nao carregou")
    text = str(err)
    assert "http" not in text
    assert "?" not in text


def test_system_migrated_carries_target_system():
    err = SystemMigrated(target_system="EPROC")
    assert err.target_system == "EPROC"
    assert err.code == "system_migrated"
