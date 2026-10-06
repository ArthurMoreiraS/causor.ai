"""Run read projections and JSON aggregates on disposable PostgreSQL in CI."""
from tests.conftest import client, seeded  # noqa: F401
from tests.test_read_egress import (  # noqa: F401
    test_compact_analysis_status_is_scoped_and_validated,
    test_confirmed_deadline_risk_boundaries,
    test_metrics_count_in_database_and_keep_deadline_review_semantics,
    test_notice_lists_keep_text_and_analysis_without_raw_payload,
)
