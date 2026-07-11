"""Promoção de perfil só com validação live recente; falha rebaixa a degraded."""

import pytest

from app.connectors.coverage import coverage_status, record_validation
from app.connectors.profiles import ConnectorCapabilities, ConnectorProfile


def _profile(status="experimental", **caps) -> ConnectorProfile:
    capabilities = ConnectorCapabilities(
        read_autos=True,
        read_secret=False,
        prepare_filing=True,
        submit_filing=False,
        download_receipt=False,
    )
    return ConnectorProfile(
        key="pje:tjmg:1",
        sistema="PJe",
        tribunal="TJMG",
        grau="1",
        url_base="https://pje.tjmg.jus.br/pje",
        filing_url=None,
        version_marker="pje-2.x",
        status=status,
        capabilities=capabilities,
    )


@pytest.fixture
def profile():
    return _profile()


@pytest.fixture
def supported_profile(db_session):
    profile = _profile(status="supported")
    record_validation(
        db_session, profile=profile, capability="read_autos", passed=True,
        documents_count=3, manifest_fingerprint="sha256:abc",
    )
    record_validation(
        db_session, profile=profile, capability="prepare_filing", passed=True,
    )
    return profile


def test_profile_cannot_be_supported_without_recent_live_read(db_session, profile):
    status = coverage_status(db_session, profile=profile, max_age_days=30)
    assert status.state == "experimental"
    assert "live_read_missing" in status.reasons


def test_profile_supported_with_recent_read_and_filing(db_session, supported_profile):
    status = coverage_status(db_session, profile=supported_profile, max_age_days=30)
    assert status.state == "supported"
    assert status.reasons == []


def test_profile_degrades_when_recent_validation_fails(db_session, supported_profile):
    record_validation(
        db_session, profile=supported_profile, capability="read_autos",
        passed=False, error_code="layout_unknown",
    )
    status = coverage_status(db_session, profile=supported_profile, max_age_days=30)
    assert status.state == "degraded"
    assert "layout_unknown" in str(status.reasons)


def test_stale_validation_falls_back_to_experimental(db_session, supported_profile):
    from datetime import datetime, timedelta, timezone

    from app.sor import models

    old = datetime.now(timezone.utc) - timedelta(days=60)
    for row in db_session.query(models.ConnectorValidation).all():
        row.tested_at = old
    db_session.flush()

    status = coverage_status(db_session, profile=supported_profile, max_age_days=30)
    assert status.state == "experimental"
    assert "live_read_missing" in status.reasons


def test_blocked_profile_stays_blocked(db_session):
    profile = _profile(status="blocked")
    status = coverage_status(db_session, profile=profile, max_age_days=30)
    assert status.state == "blocked"
