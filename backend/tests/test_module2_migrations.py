"""Prove all 6 new Module 2 Alembic revisions (025-030) apply and reverse cleanly.

Follows the pattern in `test_job_matching_migrations.py`: run against a real SQLite
file via Alembic's `upgrade`/`downgrade` commands (not `create_all`), then inspect
the resulting schema with SQLAlchemy `inspect()`.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import inspect

from alembic import command
from tests.migration_helpers import (
    alembic_config,
    sqlite_file_url,
    sync_engine_for,
    table_names,
    upgrade_head,
)

REVISION_BEFORE_MODULE2 = "024_push_subscriptions"
REV_CV_CHAT_SESSIONS = "025_cv_chat_sessions"
REV_CV_FEEDBACK_REPORTS = "026_cv_feedback_reports"
REV_PORTFOLIO_PROFILES = "027_portfolio_profiles"
REV_PORTFOLIO_ITEMS = "028_portfolio_items"
REV_JOB_SWIPE_ACTIONS = "029_job_swipe_actions"
REV_OUTREACH_MESSAGES = "030_outreach_messages"

MODULE2_TABLES = {
    "cv_chat_sessions",
    "cv_chat_messages",
    "cv_feedback_reports",
    "portfolio_profiles",
    "portfolio_items",
    "job_swipe_actions",
    "outreach_messages",
}


@pytest.fixture
def sqlite_url(tmp_path: Path) -> str:
    return sqlite_file_url(tmp_path / "module2_migrate.db")


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


class TestUpgradeHeadCreatesAllModule2Tables:
    def test_all_seven_tables_exist(self, sqlite_url: str):
        upgrade_head(sqlite_url)
        names = table_names(sqlite_url)
        assert MODULE2_TABLES <= names


class TestCvChatSchema:
    def test_cv_chat_sessions_columns(self, sqlite_url: str):
        upgrade_head(sqlite_url)
        cols = _columns(sqlite_url, "cv_chat_sessions")
        expected = {
            "id",
            "user_id",
            "document_id",
            "status",
            "missing_fields_at_start",
            "fields_resolved",
            "started_at",
            "completed_at",
        }
        assert expected <= cols.keys()
        assert cols["user_id"]["nullable"] is False
        assert cols["document_id"]["nullable"] is False
        assert cols["status"]["nullable"] is False
        assert cols["completed_at"]["nullable"] is True

    def test_cv_chat_sessions_foreign_keys(self, sqlite_url: str):
        upgrade_head(sqlite_url)
        fks = _foreign_keys(sqlite_url, "cv_chat_sessions")
        referred_tables = {fk["referred_table"] for fk in fks}
        assert "users" in referred_tables
        assert "candidate_documents" in referred_tables

    def test_cv_chat_messages_columns(self, sqlite_url: str):
        upgrade_head(sqlite_url)
        cols = _columns(sqlite_url, "cv_chat_messages")
        expected = {
            "id",
            "session_id",
            "role",
            "content",
            "field_name",
            "tool_call_result",
            "created_at",
        }
        assert expected <= cols.keys()
        assert cols["role"]["nullable"] is False
        assert cols["content"]["nullable"] is False
        assert cols["field_name"]["nullable"] is True

    def test_cv_chat_messages_fk_to_sessions(self, sqlite_url: str):
        upgrade_head(sqlite_url)
        fks = _foreign_keys(sqlite_url, "cv_chat_messages")
        assert any(fk["referred_table"] == "cv_chat_sessions" for fk in fks)


class TestCvFeedbackReportsSchema:
    def test_columns(self, sqlite_url: str):
        upgrade_head(sqlite_url)
        cols = _columns(sqlite_url, "cv_feedback_reports")
        expected = {
            "id",
            "document_id",
            "user_id",
            "target_role",
            "ats_score",
            "strengths",
            "improvements",
            "rewritten_bullets",
            "accepted_bullet_indices",
            "created_at",
        }
        assert expected <= cols.keys()
        assert cols["ats_score"]["nullable"] is False
        assert cols["target_role"]["nullable"] is True

    def test_foreign_keys(self, sqlite_url: str):
        upgrade_head(sqlite_url)
        fks = _foreign_keys(sqlite_url, "cv_feedback_reports")
        referred_tables = {fk["referred_table"] for fk in fks}
        assert "candidate_documents" in referred_tables
        assert "users" in referred_tables

    def test_indexes(self, sqlite_url: str):
        upgrade_head(sqlite_url)
        indexes = {ix["name"]: ix for ix in _indexes(sqlite_url, "cv_feedback_reports")}
        assert indexes["ix_cv_feedback_reports_document_id"]["column_names"] == ["document_id"]
        assert indexes["ix_cv_feedback_reports_user_id"]["column_names"] == ["user_id"]


class TestPortfolioSchema:
    def test_portfolio_profiles_columns(self, sqlite_url: str):
        upgrade_head(sqlite_url)
        cols = _columns(sqlite_url, "portfolio_profiles")
        expected = {
            "id",
            "user_id",
            "slug",
            "display_name",
            "headline",
            "bio",
            "is_published",
            "created_at",
            "updated_at",
        }
        assert expected <= cols.keys()
        assert cols["user_id"]["nullable"] is False
        assert cols["slug"]["nullable"] is False
        assert cols["is_published"]["nullable"] is False

    def test_portfolio_profiles_slug_and_user_id_unique(self, sqlite_url: str):
        upgrade_head(sqlite_url)
        engine = sync_engine_for(sqlite_url)
        try:
            with engine.connect() as conn:
                unique_constraints = inspect(conn).get_unique_constraints("portfolio_profiles")
                indexes = inspect(conn).get_indexes("portfolio_profiles")
        finally:
            engine.dispose()
        unique_columns = {tuple(uc["column_names"]) for uc in unique_constraints}
        unique_columns |= {tuple(ix["column_names"]) for ix in indexes if ix["unique"]}
        assert ("slug",) in unique_columns
        assert ("user_id",) in unique_columns

    def test_portfolio_items_columns(self, sqlite_url: str):
        upgrade_head(sqlite_url)
        cols = _columns(sqlite_url, "portfolio_items")
        expected = {
            "id",
            "profile_id",
            "item_type",
            "title",
            "description",
            "url",
            "display_order",
            "created_at",
        }
        assert expected <= cols.keys()
        assert cols["profile_id"]["nullable"] is False
        assert cols["title"]["nullable"] is False
        assert cols["url"]["nullable"] is False

    def test_portfolio_items_fk_to_profiles(self, sqlite_url: str):
        upgrade_head(sqlite_url)
        fks = _foreign_keys(sqlite_url, "portfolio_items")
        assert any(fk["referred_table"] == "portfolio_profiles" for fk in fks)


class TestJobSwipeActionsSchema:
    def test_columns(self, sqlite_url: str):
        upgrade_head(sqlite_url)
        cols = _columns(sqlite_url, "job_swipe_actions")
        expected = {"id", "job_match_id", "user_id", "direction", "created_at"}
        assert expected <= cols.keys()
        assert cols["job_match_id"]["nullable"] is False
        assert cols["direction"]["nullable"] is False

    def test_job_match_id_is_unique_and_fk(self, sqlite_url: str):
        upgrade_head(sqlite_url)
        fks = _foreign_keys(sqlite_url, "job_swipe_actions")
        assert any(fk["referred_table"] == "job_matches" for fk in fks)
        indexes = {ix["name"]: ix for ix in _indexes(sqlite_url, "job_swipe_actions")}
        assert bool(indexes["ix_job_swipe_actions_job_match_id"]["unique"])


class TestOutreachMessagesSchema:
    def test_columns(self, sqlite_url: str):
        upgrade_head(sqlite_url)
        cols = _columns(sqlite_url, "outreach_messages")
        expected = {
            "id",
            "user_id",
            "job_match_id",
            "recipient_role_title",
            "company_name",
            "subject",
            "body",
            "company_context_used",
            "status",
            "sent_at",
            "created_at",
        }
        assert expected <= cols.keys()
        assert cols["user_id"]["nullable"] is False
        assert cols["company_name"]["nullable"] is False
        assert cols["subject"]["nullable"] is False
        assert cols["body"]["nullable"] is False
        assert cols["job_match_id"]["nullable"] is True

    def test_foreign_keys(self, sqlite_url: str):
        upgrade_head(sqlite_url)
        fks = _foreign_keys(sqlite_url, "outreach_messages")
        referred_tables = {fk["referred_table"] for fk in fks}
        assert "users" in referred_tables
        assert "job_matches" in referred_tables

    def test_indexes(self, sqlite_url: str):
        upgrade_head(sqlite_url)
        indexes = {ix["name"]: ix for ix in _indexes(sqlite_url, "outreach_messages")}
        assert indexes["ix_outreach_messages_user_id"]["column_names"] == ["user_id"]
        assert indexes["ix_outreach_messages_status"]["column_names"] == ["status"]


class TestDowngrades:
    """Downgrade each of the 6 revisions in reverse order and confirm it cleanly
    drops exactly what its own `upgrade()` created, without erroring.
    """

    def test_downgrade_030_outreach_messages_drops_only_that_table(self, sqlite_url: str):
        upgrade_head(sqlite_url)
        _downgrade_to(sqlite_url, REV_JOB_SWIPE_ACTIONS)
        names = table_names(sqlite_url)
        assert "outreach_messages" not in names
        assert {"cv_chat_sessions", "cv_feedback_reports", "portfolio_profiles", "job_swipe_actions"} <= names

    def test_downgrade_029_job_swipe_actions_drops_only_that_table(self, sqlite_url: str):
        upgrade_head(sqlite_url)
        _downgrade_to(sqlite_url, REV_JOB_SWIPE_ACTIONS)
        _downgrade_to(sqlite_url, REV_PORTFOLIO_ITEMS)
        names = table_names(sqlite_url)
        assert "job_swipe_actions" not in names
        assert "portfolio_items" in names

    def test_downgrade_028_portfolio_items_drops_only_that_table(self, sqlite_url: str):
        upgrade_head(sqlite_url)
        _downgrade_to(sqlite_url, REV_PORTFOLIO_ITEMS)
        _downgrade_to(sqlite_url, REV_PORTFOLIO_PROFILES)
        names = table_names(sqlite_url)
        assert "portfolio_items" not in names
        assert "portfolio_profiles" in names

    def test_downgrade_027_portfolio_profiles_drops_only_that_table(self, sqlite_url: str):
        upgrade_head(sqlite_url)
        _downgrade_to(sqlite_url, REV_PORTFOLIO_ITEMS)
        _downgrade_to(sqlite_url, REV_PORTFOLIO_PROFILES)
        _downgrade_to(sqlite_url, REV_CV_FEEDBACK_REPORTS)
        names = table_names(sqlite_url)
        assert "portfolio_profiles" not in names
        assert "cv_feedback_reports" in names

    def test_downgrade_026_cv_feedback_reports_drops_only_that_table(self, sqlite_url: str):
        upgrade_head(sqlite_url)
        _downgrade_to(sqlite_url, REV_CV_FEEDBACK_REPORTS)
        _downgrade_to(sqlite_url, REV_CV_CHAT_SESSIONS)
        names = table_names(sqlite_url)
        assert "cv_feedback_reports" not in names
        assert {"cv_chat_sessions", "cv_chat_messages"} <= names

    def test_downgrade_025_cv_chat_drops_both_its_tables(self, sqlite_url: str):
        upgrade_head(sqlite_url)
        _downgrade_to(sqlite_url, REV_CV_CHAT_SESSIONS)
        _downgrade_to(sqlite_url, REVISION_BEFORE_MODULE2)
        names = table_names(sqlite_url)
        assert not {"cv_chat_sessions", "cv_chat_messages"} & names
        # Unrelated pre-existing tables from earlier migrations must survive.
        assert {"users", "candidate_documents", "job_matches"} <= names

    def test_full_downgrade_then_reupgrade_is_clean(self, sqlite_url: str):
        """Downgrading straight from head to before 025, then re-upgrading to head,
        should reproduce the exact same 7 tables (guards against a migration that
        only works once).
        """
        upgrade_head(sqlite_url)
        _downgrade_to(sqlite_url, REVISION_BEFORE_MODULE2)
        names_after_downgrade = table_names(sqlite_url)
        assert not (MODULE2_TABLES & names_after_downgrade)

        upgrade_head(sqlite_url)
        names_after_reupgrade = table_names(sqlite_url)
        assert MODULE2_TABLES <= names_after_reupgrade


def test_module2_migrations_upgrade_and_downgrade_cleanly(sqlite_url: str):
    """Upgrade to head (includes all Module 2 revisions), then downgrade back past them.

    Uses the same alembic_config fixture the existing migration tests use
    (backend/tests/migration_helpers.py's upgrade_head, already imported by conftest.py).
    """
    upgrade_head(sqlite_url)
    command.downgrade(alembic_config(sqlite_url), "024_push_subscriptions")  # back to just before Module 2
    upgrade_head(sqlite_url)  # re-apply, proving idempotent forward path

    names = table_names(sqlite_url)
    assert MODULE2_TABLES <= names
