"""The same fencing and IO contracts on real PostgreSQL connections/migrations."""

from tests.test_document_leases import (  # noqa: F401
    test_expired_owner_cannot_renew_or_publish_after_reclaim,
    test_fresh_lease_is_not_recovered_by_old_updated_at,
    test_document_lease_never_renews_filing_job,
)
from tests.test_document_checkpoints import (  # noqa: F401
    local_store,
    test_io_runs_without_sessions_and_stale_results_cannot_publish,
    test_background_heartbeat_renews_with_its_own_short_session,
)
