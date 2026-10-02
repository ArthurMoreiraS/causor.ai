"""Reuse assisted work scenarios on actual migrated PostgreSQL constraints/FTS."""
from tests.test_legal_work import (  # noqa: F401
    test_deadline_confirmation_keeps_source_analysis_current,
    test_deadline_edit_during_draft_rejects_without_petition,
    test_deadline_description_edit_during_draft_rejects_without_petition,
    test_linked_notice_and_sor_history_reach_analysis,
    test_long_sor_history_marks_individual_text_truncation,
    test_notice_edit_during_analysis_rejects_result,
    test_notice_edit_during_draft_rejects_without_petition,
    test_process_metadata_and_history_edits_during_analysis_reject_result,
    test_repeated_own_draft_is_excluded_from_source_snapshot,
    test_work_drafts_without_fabricating_notice_and_requires_evidence_review,
    test_changed_documents_invalidate_evidence_review,
    test_edit_during_model_call_does_not_publish_stale_evidence,
    test_scope_is_explicit_and_versioned,
    test_gap_task_is_linked_deduplicated_and_version_checked,
)
from tests.test_original_evidence import (  # noqa: F401
    test_recovers_fact_absent_from_summary_and_excludes_non_manifest_version,
    test_pinned_source_must_belong_to_snapshot,
)
from tests.test_filing_packages import (  # noqa: F401
    package_work,
    test_package_requires_exact_approval_and_export_preserves_bytes,
    test_edit_after_approval_blocks_export_and_replacement_requires_approval,
    test_attempt_deduplicates_and_never_marks_export_as_filed,
    test_wrong_receipt_cannot_confirm_and_correct_receipt_requires_human_review,
    test_reverting_text_does_not_restore_approval,
    test_active_attempt_freezes_draft_and_legacy_routes_cannot_bypass_review,
)
from tests.test_executor_guards import (  # noqa: F401
    test_claim_respects_identity_target_and_capabilities,
    test_after_submit_checkpoint_failure_is_uncertain_and_not_claimable,
)


def test_migrations_roundtrip_preserve_legacy_process(pg_engine, db_session, seeded):
    from tests.postgres.conftest import migrate
    from sqlalchemy import text
    number, process_id = seeded.numero, seeded.id
    db_session.commit()
    migrate(pg_engine, "a7d3f9b5c1e4", downgrade=True)
    migrate(pg_engine)
    with pg_engine.connect() as connection:
        assert connection.execute(text("select numero from processo where id = :id"), {"id": process_id}).scalar_one() == number
        assert connection.execute(text("select count(*) from trabalho_juridico")).scalar_one() == 0
        assert connection.execute(text("select count(*) from tentativa_protocolo")).scalar_one() == 0


def test_concurrent_external_attempts_create_one_record(client, db_session, seeded, pg_engine, request):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from sqlalchemy.orm import Session
    from sqlalchemy import select, func
    from tests.test_filing_packages import make_package, approve
    from app.api.package_routes import AttemptIn, start_external_attempt
    from app.auth.jwt_auth import CurrentUser
    from app.sor import models
    package = approve(client, make_package(client, request.getfixturevalue("package_work"), seeded))
    user = db_session.scalar(select(models.Usuario).where(models.Usuario.escritorio_id == seeded.escritorio_id))
    principal = CurrentUser(usuario_id=user.id, escritorio_id=user.escritorio_id, email=user.email)
    db_session.commit()
    barrier = Barrier(2)
    def start(index):
        with Session(pg_engine) as session:
            barrier.wait(timeout=5)
            return start_external_attempt(package["id"], AttemptIn(fingerprint=package["fingerprint"],
                idempotency_key=f"concurrent-attempt-{index}"), session, principal)["id"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(start, range(2)))
    assert results[0] == results[1]
    assert db_session.scalar(select(func.count()).select_from(models.TentativaProtocolo)) == 1
