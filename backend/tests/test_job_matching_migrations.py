"""Schema-verification tests for the job-matching migrations (018-021).

Follows the pattern in `test_alembic_migrations.py`: run against a real
SQLite file via Alembic's `upgrade`/`downgrade` commands (not `create_all`),
then inspect the resulting schema with SQLAlchemy `inspect()`. SQLite is the
local/test dialect for this module (see models.py's PGVECTOR_AVAILABLE
fallback), so these tests intentionally exercise the SQLite branch of each
migration's `upgrade()`/`downgrade()`.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from sqlalchemy import inspect
from sqlalchemy import text as sa_text

from tests.migration_helpers import (
    alembic_config,
    sqlite_file_url,
    sync_engine_for,
    table_names,
    upgrade_head,
)

REVISION_BEFORE_JOB_MATCHING = "017_practice_audio_recordings"
REV_JOB_POSTINGS = "018_job_postings"
REV_JOB_POSTING_EMBEDDINGS = "019_job_posting_embeddings"
REV_CANDIDATE_JOB_PREFERENCES = "020_candidate_job_preferences"
REV_JOB_MATCHES = "021_job_matches"
REV_WEBHOOK_URL_PREFERENCES = "022_webhook_url_preferences"
REV_JOB_MATCH_EXPLANATION_STATUS = "023_job_match_explanation_status"
REV_PUSH_SUBSCRIPTIONS = "024_push_subscriptions"


@pytest.fixture
def sqlite_url(tmp_path: Path) -> str:
    return sqlite_file_url(tmp_path / "job_matching_migrate.db")


def _columns(url: str, table: str) -> dict[str, dict]:
    engine = sync_engine_for(url)
    try:
        with engine.connect() as conn:
            return {c["name"]: c for c in inspect(conn).get_columns(table)}
    finally:
        engine.dispose()


def _indexes(url: str, table: str) -> list[dict]:
    engine = sync_engine_for(url)
    try:
        with engine.connect() as conn:
            return inspect(conn).get_indexes(table)
    finally:
        engine.dispose()


def _foreign_keys(url: str, table: str) -> list[dict]:
    engine = sync_engine_for(url)
    try:
        with engine.connect() as conn:
            return inspect(conn).get_foreign_keys(table)
    finally:
        engine.dispose()


def _downgrade_to(url: str, revision: str) -> None:
    command.downgrade(alembic_config(url), revision)


class TestUpgradeHeadCreatesAllFourTables:
    def test_all_four_tables_exist(self, sqlite_url: str):
        upgrade_head(sqlite_url)
        names = table_names(sqlite_url)
        assert {
            "job_postings",
            "job_posting_embeddings",
            "candidate_job_preferences",
            "job_matches",
        } <= names


class TestJobPostingsSchema:
    def test_columns(self, sqlite_url: str):
        upgrade_head(sqlite_url)
        cols = _columns(sqlite_url, "job_postings")
        expected = {
            "id",
            "dedup_key",
            "title",
            "company",
            "location",
            "remote",
            "source",
            "source_url",
            "description_raw",
            "salary_min",
            "salary_max",
            "salary_currency",
            "posted_at",
            "first_seen_at",
            "last_seen_at",
            "sources_seen",
            "is_active",
        }
        assert expected <= cols.keys()
        assert cols["dedup_key"]["nullable"] is False
        assert cols["title"]["nullable"] is False
        assert cols["company"]["nullable"] is False
        assert cols["location"]["nullable"] is True
        assert cols["remote"]["nullable"] is False
        assert cols["is_active"]["nullable"] is False

    def test_indexes(self, sqlite_url: str):
        upgrade_head(sqlite_url)
        indexes = {ix["name"]: ix for ix in _indexes(sqlite_url, "job_postings")}
        assert bool(indexes["ix_job_postings_dedup_key"]["unique"])
        assert indexes["ix_job_postings_dedup_key"]["column_names"] == ["dedup_key"]
        assert indexes["ix_job_postings_is_active"]["column_names"] == ["is_active"]
        assert indexes["ix_job_postings_last_seen_at"]["column_names"] == ["last_seen_at"]


class TestJobPostingEmbeddingsSchema:
    def test_columns_sqlite_fallback(self, sqlite_url: str):
        """SQLite has no pgvector, so 019's `else` branch (Text-encoded embedding) applies."""
        upgrade_head(sqlite_url)
        cols = _columns(sqlite_url, "job_posting_embeddings")
        expected = {"id", "job_posting_id", "embedding", "token_count", "created_at"}
        assert expected <= cols.keys()
        assert cols["job_posting_id"]["nullable"] is False
        assert cols["embedding"]["nullable"] is False
        assert cols["token_count"]["nullable"] is False

    def test_job_posting_id_is_unique_and_fk_to_job_postings(self, sqlite_url: str):
        upgrade_head(sqlite_url)
        fks = _foreign_keys(sqlite_url, "job_posting_embeddings")
        assert any(
            fk["referred_table"] == "job_postings"
            and fk["constrained_columns"] == ["job_posting_id"]
            for fk in fks
        )
        # SQLite's `unique=True` on the column produces a unique index rather than
        # a named ix_* index (no explicit op.create_index call in 019's SQLite branch).
        engine = sync_engine_for(sqlite_url)
        try:
            with engine.connect() as conn:
                unique_constraints = inspect(conn).get_unique_constraints("job_posting_embeddings")
                indexes = inspect(conn).get_indexes("job_posting_embeddings")
        finally:
            engine.dispose()
        has_unique_posting_id = any(
            uc["column_names"] == ["job_posting_id"] for uc in unique_constraints
        ) or any(ix["column_names"] == ["job_posting_id"] and bool(ix["unique"]) for ix in indexes)
        assert has_unique_posting_id


class TestCandidateJobPreferencesSchema:
    def test_columns(self, sqlite_url: str):
        upgrade_head(sqlite_url)
        cols = _columns(sqlite_url, "candidate_job_preferences")
        expected = {
            "id",
            "user_id",
            "source_document_id",
            "desired_roles",
            "desired_locations",
            "remote_preference",
            "salary_min",
            "salary_max",
            "salary_currency",
            "notification_channels",
            "digest_frequency",
            "is_scan_enabled",
            "last_scanned_at",
            "created_at",
            "updated_at",
        }
        assert expected <= cols.keys()
        assert cols["user_id"]["nullable"] is False
        assert cols["salary_currency"]["nullable"] is False
        assert cols["is_scan_enabled"]["nullable"] is False

    def test_foreign_keys(self, sqlite_url: str):
        upgrade_head(sqlite_url)
        fks = _foreign_keys(sqlite_url, "candidate_job_preferences")
        referred_tables = {fk["referred_table"] for fk in fks}
        assert "users" in referred_tables
        assert "candidate_documents" in referred_tables
        user_fk = next(fk for fk in fks if fk["referred_table"] == "users")
        assert user_fk["constrained_columns"] == ["user_id"]
        doc_fk = next(fk for fk in fks if fk["referred_table"] == "candidate_documents")
        assert doc_fk["constrained_columns"] == ["source_document_id"]

    def test_indexes(self, sqlite_url: str):
        upgrade_head(sqlite_url)
        indexes = {ix["name"]: ix for ix in _indexes(sqlite_url, "candidate_job_preferences")}
        assert bool(indexes["ix_candidate_job_preferences_user_id"]["unique"])
        assert indexes["ix_candidate_job_preferences_user_id"]["column_names"] == ["user_id"]
        assert indexes["ix_candidate_job_preferences_scan_enabled"]["column_names"] == [
            "is_scan_enabled"
        ]


class TestJobMatchesSchema:
    def test_columns(self, sqlite_url: str):
        upgrade_head(sqlite_url)
        cols = _columns(sqlite_url, "job_matches")
        expected = {
            "id",
            "user_id",
            "job_posting_id",
            "similarity_score",
            "rule_score",
            "overall_score",
            "score_breakdown",
            "explanation",
            "explanation_generated_at",
            "notified_at",
            "viewed_at",
            "feedback",
            "created_at",
        }
        assert expected <= cols.keys()
        assert cols["user_id"]["nullable"] is False
        assert cols["job_posting_id"]["nullable"] is False
        assert cols["similarity_score"]["nullable"] is False
        assert cols["rule_score"]["nullable"] is False
        assert cols["overall_score"]["nullable"] is False
        assert cols["explanation"]["nullable"] is True
        assert cols["feedback"]["nullable"] is True

    def test_foreign_keys(self, sqlite_url: str):
        upgrade_head(sqlite_url)
        fks = _foreign_keys(sqlite_url, "job_matches")
        referred_tables = {fk["referred_table"] for fk in fks}
        assert "users" in referred_tables
        assert "job_postings" in referred_tables

    def test_indexes(self, sqlite_url: str):
        upgrade_head(sqlite_url)
        indexes = {ix["name"]: ix for ix in _indexes(sqlite_url, "job_matches")}
        assert indexes["ix_job_matches_user_id"]["column_names"] == ["user_id"]
        assert indexes["ix_job_matches_job_posting_id"]["column_names"] == ["job_posting_id"]
        assert indexes["ix_job_matches_overall_score"]["column_names"] == ["overall_score"]
        unique_index = indexes["ix_job_matches_user_posting"]
        assert bool(unique_index["unique"])
        assert set(unique_index["column_names"]) == {"user_id", "job_posting_id"}


class TestJobMatchExplanationStatusSchema:
    """Revision 023: explanation retry state machine columns on job_matches."""

    def test_columns_have_correct_types_and_defaults(self, sqlite_url: str):
        upgrade_head(sqlite_url)
        cols = _columns(sqlite_url, "job_matches")
        expected = {"explanation_status", "last_error", "is_error", "retry_count"}
        assert expected <= cols.keys()

        assert cols["explanation_status"]["nullable"] is False
        assert cols["last_error"]["nullable"] is True
        assert cols["is_error"]["nullable"] is False
        assert cols["retry_count"]["nullable"] is False

    def test_backfill_marks_preexisting_explained_rows(self, sqlite_url: str):
        """A row inserted at revision 022 (before this column existed) with a non-null
        `explanation` must come out of `upgrade()` with `explanation_status='explained'`."""
        command.upgrade(alembic_config(sqlite_url), REV_WEBHOOK_URL_PREFERENCES)

        engine = sync_engine_for(sqlite_url)
        match_id = "11111111-1111-1111-1111-111111111111"
        try:
            with engine.begin() as conn:
                conn.execute(
                    sa_text(
                        """
                        INSERT INTO job_matches (
                            id, user_id, job_posting_id, similarity_score, rule_score,
                            overall_score, score_breakdown, explanation,
                            explanation_generated_at, created_at
                        ) VALUES (
                            :id, :user_id, :job_posting_id, 0.5, 0.5, 50.0, '{}',
                            'Already explained before this migration existed.',
                            NULL, CURRENT_TIMESTAMP
                        )
                        """
                    ),
                    {
                        "id": match_id,
                        "user_id": "22222222-2222-2222-2222-222222222222",
                        "job_posting_id": "33333333-3333-3333-3333-333333333333",
                    },
                )
        finally:
            engine.dispose()

        command.upgrade(alembic_config(sqlite_url), REV_JOB_MATCH_EXPLANATION_STATUS)

        engine = sync_engine_for(sqlite_url)
        try:
            with engine.connect() as conn:
                row = conn.execute(
                    sa_text("SELECT explanation_status FROM job_matches WHERE id = :id"),
                    {"id": match_id},
                ).fetchone()
        finally:
            engine.dispose()

        assert row is not None
        assert row[0] == "explained"

    def test_downgrade_drops_all_four_columns(self, sqlite_url: str):
        upgrade_head(sqlite_url)
        _downgrade_to(sqlite_url, REV_WEBHOOK_URL_PREFERENCES)
        cols = _columns(sqlite_url, "job_matches")
        assert not {"explanation_status", "last_error", "is_error", "retry_count"} & cols.keys()
        # The table itself, and its pre-existing columns, must survive.
        assert "explanation" in cols

    def test_full_downgrade_then_reupgrade_is_clean(self, sqlite_url: str):
        upgrade_head(sqlite_url)
        _downgrade_to(sqlite_url, REV_WEBHOOK_URL_PREFERENCES)
        cols_after_downgrade = _columns(sqlite_url, "job_matches")
        assert (
            not {
                "explanation_status",
                "last_error",
                "is_error",
                "retry_count",
            }
            & cols_after_downgrade.keys()
        )

        upgrade_head(sqlite_url)
        cols_after_reupgrade = _columns(sqlite_url, "job_matches")
        assert {
            "explanation_status",
            "last_error",
            "is_error",
            "retry_count",
        } <= cols_after_reupgrade.keys()


class TestPushSubscriptionsSchema:
    """Revision 024: push_subscriptions table for browser push notification delivery."""

    def test_table_exists(self, sqlite_url: str):
        upgrade_head(sqlite_url)
        names = table_names(sqlite_url)
        assert "push_subscriptions" in names

    def test_columns(self, sqlite_url: str):
        upgrade_head(sqlite_url)
        cols = _columns(sqlite_url, "push_subscriptions")
        expected = {
            "id",
            "user_id",
            "endpoint",
            "p256dh_key",
            "auth_key",
            "created_at",
            "last_used_at",
        }
        assert expected <= cols.keys()
        assert cols["user_id"]["nullable"] is False
        assert cols["endpoint"]["nullable"] is False
        assert cols["p256dh_key"]["nullable"] is False
        assert cols["auth_key"]["nullable"] is False
        assert cols["created_at"]["nullable"] is False
        assert cols["last_used_at"]["nullable"] is True

    def test_foreign_key_to_users(self, sqlite_url: str):
        upgrade_head(sqlite_url)
        fks = _foreign_keys(sqlite_url, "push_subscriptions")
        referred_tables = {fk["referred_table"] for fk in fks}
        assert "users" in referred_tables
        user_fk = next(fk for fk in fks if fk["referred_table"] == "users")
        assert user_fk["constrained_columns"] == ["user_id"]

    def test_indexes(self, sqlite_url: str):
        upgrade_head(sqlite_url)
        indexes = {ix["name"]: ix for ix in _indexes(sqlite_url, "push_subscriptions")}
        assert indexes["ix_push_subscriptions_user_id"]["column_names"] == ["user_id"]
        endpoint_index = indexes["ix_push_subscriptions_endpoint"]
        assert bool(endpoint_index["unique"])
        assert endpoint_index["column_names"] == ["endpoint"]

    def test_downgrade_drops_only_push_subscriptions(self, sqlite_url: str):
        upgrade_head(sqlite_url)
        _downgrade_to(sqlite_url, REV_JOB_MATCH_EXPLANATION_STATUS)
        names = table_names(sqlite_url)
        assert "push_subscriptions" not in names
        assert {
            "job_postings",
            "job_posting_embeddings",
            "candidate_job_preferences",
            "job_matches",
        } <= names

    def test_full_downgrade_then_reupgrade_is_clean(self, sqlite_url: str):
        upgrade_head(sqlite_url)
        _downgrade_to(sqlite_url, REV_JOB_MATCH_EXPLANATION_STATUS)
        names_after_downgrade = table_names(sqlite_url)
        assert "push_subscriptions" not in names_after_downgrade

        upgrade_head(sqlite_url)
        names_after_reupgrade = table_names(sqlite_url)
        assert "push_subscriptions" in names_after_reupgrade


class TestDowngrades:
    """Downgrade each of the 4 revisions in reverse order and confirm it cleanly
    drops exactly what its own `upgrade()` created, without erroring.
    """

    def test_downgrade_021_job_matches_drops_only_job_matches(self, sqlite_url: str):
        upgrade_head(sqlite_url)
        _downgrade_to(sqlite_url, REV_CANDIDATE_JOB_PREFERENCES)
        names = table_names(sqlite_url)
        assert "job_matches" not in names
        assert {"job_postings", "job_posting_embeddings", "candidate_job_preferences"} <= names

    def test_downgrade_020_candidate_job_preferences_drops_only_that_table(self, sqlite_url: str):
        upgrade_head(sqlite_url)
        _downgrade_to(sqlite_url, REV_CANDIDATE_JOB_PREFERENCES)
        _downgrade_to(sqlite_url, REV_JOB_POSTING_EMBEDDINGS)
        names = table_names(sqlite_url)
        assert "candidate_job_preferences" not in names
        assert {"job_postings", "job_posting_embeddings"} <= names

    def test_downgrade_019_job_posting_embeddings_drops_only_that_table(self, sqlite_url: str):
        upgrade_head(sqlite_url)
        _downgrade_to(sqlite_url, REV_CANDIDATE_JOB_PREFERENCES)
        _downgrade_to(sqlite_url, REV_JOB_POSTING_EMBEDDINGS)
        _downgrade_to(sqlite_url, REV_JOB_POSTINGS)
        names = table_names(sqlite_url)
        assert "job_posting_embeddings" not in names
        assert "job_postings" in names

    def test_downgrade_018_job_postings_drops_table_and_its_indexes(self, sqlite_url: str):
        upgrade_head(sqlite_url)
        _downgrade_to(sqlite_url, REV_CANDIDATE_JOB_PREFERENCES)
        _downgrade_to(sqlite_url, REV_JOB_POSTING_EMBEDDINGS)
        _downgrade_to(sqlite_url, REV_JOB_POSTINGS)
        _downgrade_to(sqlite_url, REVISION_BEFORE_JOB_MATCHING)
        names = table_names(sqlite_url)
        assert "job_postings" not in names
        # Unrelated pre-existing tables from earlier migrations must survive.
        assert {"users", "candidate_documents"} <= names

    def test_full_downgrade_then_reupgrade_is_clean(self, sqlite_url: str):
        """Downgrading straight from head to before 018, then re-upgrading to head,
        should reproduce the exact same 4 tables (guards against a migration that
        only works once).
        """
        upgrade_head(sqlite_url)
        _downgrade_to(sqlite_url, REVISION_BEFORE_JOB_MATCHING)
        names_after_downgrade = table_names(sqlite_url)
        assert (
            not {
                "job_postings",
                "job_posting_embeddings",
                "candidate_job_preferences",
                "job_matches",
            }
            & names_after_downgrade
        )

        upgrade_head(sqlite_url)
        names_after_reupgrade = table_names(sqlite_url)
        assert {
            "job_postings",
            "job_posting_embeddings",
            "candidate_job_preferences",
            "job_matches",
        } <= names_after_reupgrade
