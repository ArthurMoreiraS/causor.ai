"""Estado de cobertura de um perfil a partir de validações live persistidas.

Regra central: nenhum perfil vira ``supported`` por edição manual — só por
validação live recente (leitura + preparo) sem falha posterior. Uma falha
recente rebaixa para ``degraded``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.capture.court_routing import known_routes
from app.connectors.profiles import ConnectorCapabilities, ConnectorProfile
from app.settings import settings
from app.sor import models


@dataclass(frozen=True)
class CoverageStatus:
    profile_key: str
    state: str  # experimental | supported | degraded | blocked
    reasons: list[str]
    last_validation_at: datetime | None


def _profile_key(sistema: str, tribunal: str, grau: str) -> str:
    return f"{sistema.casefold()}:{tribunal.upper()}:{grau}"


def known_profiles() -> list[ConnectorProfile]:
    """Perfis candidatos derivados do registro de roteamento.

    Todos nascem ``experimental`` com preparo somente (``submit_filing=False``);
    a promoção depende de validação live persistida, nunca de código existir."""
    profiles: list[ConnectorProfile] = []
    for route in known_routes():
        profiles.append(
            ConnectorProfile(
                key=_profile_key(route.sistema, route.tribunal, route.grau),
                sistema=route.sistema,
                tribunal=route.tribunal,
                grau=route.grau,
                url_base=route.url_login or "",
                filing_url=route.url_peticionamento,
                version_marker="unverified",
                status="experimental",
                capabilities=ConnectorCapabilities(
                    read_autos=True,
                    read_secret=False,
                    prepare_filing=True,
                    submit_filing=False,
                    download_receipt=False,
                ),
            )
        )
    return profiles


def _now() -> datetime:
    return datetime.now(timezone.utc)


def record_validation(
    session: Session,
    *,
    profile: ConnectorProfile,
    capability: str,
    passed: bool,
    documents_count: int | None = None,
    manifest_fingerprint: str | None = None,
    error_code: str | None = None,
    evidence: dict | None = None,
    escritorio_id: int = 1,
    installation_id: int = 1,
    agent_version: str | None = None,
    app_revision: str = "dev",
    tested_at: datetime | None = None,
) -> models.ConnectorValidation:
    row = models.ConnectorValidation(
        escritorio_id=escritorio_id,
        installation_id=installation_id,
        profile_key=profile.key,
        capability=capability,
        passed=passed,
        documents_count=documents_count,
        manifest_fingerprint=manifest_fingerprint,
        error_code=error_code,
        evidence=evidence,
        agent_version=agent_version,
        app_revision=app_revision,
        tested_at=tested_at or _now(),
    )
    session.add(row)
    session.flush()
    return row


def _recent_validations(
    session: Session, *, profile_key: str, max_age_days: int
) -> list[models.ConnectorValidation]:
    cutoff = _now() - timedelta(days=max_age_days)
    rows = session.scalars(
        select(models.ConnectorValidation)
        .where(models.ConnectorValidation.profile_key == profile_key)
        .order_by(models.ConnectorValidation.tested_at)
    ).all()
    recent = []
    for row in rows:
        tested = row.tested_at
        if tested.tzinfo is None:
            tested = tested.replace(tzinfo=timezone.utc)
        if tested >= cutoff:
            recent.append(row)
    return recent


def coverage_status(
    session: Session, *, profile: ConnectorProfile, max_age_days: int | None = None
) -> CoverageStatus:
    max_age_days = (
        max_age_days
        if max_age_days is not None
        else settings.connector_validation_max_age_days
    )
    if profile.status == "blocked":
        return CoverageStatus(profile.key, "blocked", ["profile_blocked"], None)

    recent = _recent_validations(
        session, profile_key=profile.key, max_age_days=max_age_days
    )
    last_at = recent[-1].tested_at if recent else None

    # Última validação por capacidade dentro da janela.
    latest_by_capability: dict[str, models.ConnectorValidation] = {}
    for row in recent:
        latest_by_capability[row.capability] = row

    # Falha recente em qualquer capacidade rebaixa para degraded.
    failures = [row for row in latest_by_capability.values() if not row.passed]
    if failures:
        reasons = [row.error_code or f"{row.capability}_failed" for row in failures]
        return CoverageStatus(profile.key, "degraded", reasons, last_at)

    read = latest_by_capability.get("read_autos")
    filing = latest_by_capability.get("prepare_filing")
    reasons: list[str] = []
    if read is None or not (read.documents_count or 0) >= 1:
        reasons.append("live_read_missing")
    if filing is None:
        reasons.append("prepare_filing_missing")

    if not reasons:
        return CoverageStatus(profile.key, "supported", [], last_at)
    return CoverageStatus(profile.key, "experimental", reasons, last_at)
