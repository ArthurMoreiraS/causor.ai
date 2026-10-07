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
