"""API de cobertura e health-check idempotente."""

from app.connectors.health import enqueue_connector_health_checks
from app.sor import models


def test_coverage_endpoint_lists_experimental_profiles(client, seeded):
    resp = client.get("/connectors/coverage")
    assert resp.status_code == 200
    rows = resp.json()
    assert rows, "matriz de cobertura vazia"
    # nenhum perfil nasce supported: promoção exige validação live
    assert all(row["state"] in {"experimental", "supported", "degraded", "blocked"} for row in rows)
    assert all(row["state"] != "supported" for row in rows)
    assert all(row["submit_filing"] is False for row in rows)


def test_coverage_detail_404_for_unknown_profile(client, seeded):
    resp = client.get("/connectors/coverage/pje:ZZZZ:9")
    assert resp.status_code == 404


def test_health_checks_are_idempotent_per_profile_and_day(db_session, seeded):
    first = enqueue_connector_health_checks(db_session, escritorio_id=seeded.escritorio_id)
    second = enqueue_connector_health_checks(db_session, escritorio_id=seeded.escritorio_id)
    assert {c.id for c in first} == {c.id for c in second}
    # um comando health_check por perfil, sem duplicar no mesmo dia
    total = db_session.query(models.AgentCommand).filter_by(tipo="health_check").count()
    assert total == len(first)
