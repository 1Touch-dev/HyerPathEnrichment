"""Schema-verification tests for the manual_job_entries migration (043, Module 4, Module F).

Follows the pattern in `test_job_matching_migrations.py`: run against a real
SQLite file via Alembic's `upgrade`/`downgrade` commands (not `create_all`),
then inspect the resulting schema with SQLAlchemy `inspect()`.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from sqlalchemy import inspect
from sqlalchemy import text as sa_text
from sqlalchemy.exc import IntegrityError

from tests.migration_helpers import (
    alembic_config,
    sqlite_file_url,
    sync_engine_for,
    table_names,
    upgrade_head,
)

REV_INTERVIEW_SCHEDULES = "042_interview_schedules"
REV_MANUAL_JOB_ENTRIES = "043_manual_job_entries"
REV_MERGE_ADMIN_AND_MODULE4_HEADS = "044_merge_admin_and_module4_heads"
REV_CURRENT_SINGLE_HEAD = "054_linkedin_lead_conversion"


@pytest.fixture
def sqlite_url(tmp_path: Path) -> str:
    return sqlite_file_url(tmp_path / "manual_jobs_migrate.db")


def _columns(url: str, table: str) -> dict[str, dict]:
    engine = sync_engine_for(url)
    try:
        with engine.connect() as conn:
            return {c["name"]: c for c in inspect(conn).get_columns(table)}
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


def _insert_job_match(
    conn,
    *,
    match_id: str,
    user_id: str,
    job_posting_id: str | None,
    manual_job_entry_id: str | None,
) -> None:
    conn.execute(
        sa_text(
            """
            INSERT INTO job_matches (
                id, user_id, job_posting_id, manual_job_entry_id,
                similarity_score, rule_score, overall_score, score_breakdown,
                application_status, created_at
            ) VALUES (
                :id, :user_id, :job_posting_id, :manual_job_entry_id,
                0.0, 0.0, 0.0, '{}',
                'new', CURRENT_TIMESTAMP
            )
            """
        ),
        {
            "id": match_id,
            "user_id": user_id,
            "job_posting_id": job_posting_id,
            "manual_job_entry_id": manual_job_entry_id,
        },
    )


class TestManualJobEntriesTableCreated:
    def test_table_exists(self, sqlite_url: str):
        upgrade_head(sqlite_url)
        assert "manual_job_entries" in table_names(sqlite_url)

    def test_columns(self, sqlite_url: str):
        upgrade_head(sqlite_url)
        cols = _columns(sqlite_url, "manual_job_entries")
        expected = {
            "id",
            "user_id",
            "title",
            "company",
            "location",
            "source_label",
            "source_url",
            "notes",
            "created_at",
        }
        assert expected <= cols.keys()
        assert cols["user_id"]["nullable"] is False
        assert cols["title"]["nullable"] is False
        assert cols["company"]["nullable"] is False
        assert cols["location"]["nullable"] is True
        assert cols["source_url"]["nullable"] is True
        assert cols["created_at"]["nullable"] is False

    def test_foreign_key_to_users(self, sqlite_url: str):
        upgrade_head(sqlite_url)
        fks = _foreign_keys(sqlite_url, "manual_job_entries")
        assert any(fk["referred_table"] == "users" for fk in fks)


class TestJobMatchesWidenedForManualEntries:
    def test_job_posting_id_is_now_nullable(self, sqlite_url: str):
        upgrade_head(sqlite_url)
        cols = _columns(sqlite_url, "job_matches")
        assert cols["job_posting_id"]["nullable"] is True

    def test_manual_job_entry_id_column_added(self, sqlite_url: str):
        upgrade_head(sqlite_url)
        cols = _columns(sqlite_url, "job_matches")
        assert "manual_job_entry_id" in cols
        assert cols["manual_job_entry_id"]["nullable"] is True

    def test_manual_job_entry_id_fk_to_manual_job_entries(self, sqlite_url: str):
        upgrade_head(sqlite_url)
        fks = _foreign_keys(sqlite_url, "job_matches")
        assert any(fk["referred_table"] == "manual_job_entries" for fk in fks)

    def test_a_manual_entry_row_with_null_job_posting_id_is_accepted(self, sqlite_url: str):
        """The whole point of this migration: a JobMatch with job_posting_id=NULL
        and manual_job_entry_id set must be insertable."""
        upgrade_head(sqlite_url)
        engine = sync_engine_for(sqlite_url)
        try:
            with engine.begin() as conn:
                conn.execute(
                    sa_text(
                        """
                        INSERT INTO users (
                            id, email, first_name, last_name, is_active, is_verified,
                            created_at, updated_at
                        )
                        VALUES (
                            :id, :email, 'Test', 'User', 1, 1,
                            CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                        )
                        """
                    ),
                    {"id": "u1", "email": "manual-jobs-migration@example.com"},
                )
                conn.execute(
                    sa_text(
                        """
                        INSERT INTO manual_job_entries (id, user_id, title, company, created_at)
                        VALUES ('m1', 'u1', 'Backend Engineer', 'Acme', CURRENT_TIMESTAMP)
                        """
                    )
                )
                _insert_job_match(
                    conn,
                    match_id="jm1",
                    user_id="u1",
                    job_posting_id=None,
                    manual_job_entry_id="m1",
                )
        finally:
            engine.dispose()

        engine = sync_engine_for(sqlite_url)
        try:
            with engine.connect() as conn:
                row = conn.execute(
                    sa_text(
                        "SELECT job_posting_id, manual_job_entry_id FROM job_matches WHERE id = 'jm1'"
                    )
                ).fetchone()
        finally:
            engine.dispose()
        assert row is not None
        assert row[0] is None
        assert row[1] == "m1"


class TestExactlyOneSourceCheckConstraint:
    """§10.2's CHECK constraint: exactly one of job_posting_id/manual_job_entry_id."""

    def _seed_user_and_manual_entry(self, conn) -> None:
        conn.execute(
            sa_text(
                """
                INSERT INTO users (
                    id, email, first_name, last_name, is_active, is_verified,
                    created_at, updated_at
                )
                VALUES (
                    'u1', 'manual-jobs-check@example.com', 'Test', 'User', 1, 1,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
                """
            )
        )
        conn.execute(
            sa_text(
                """
                INSERT INTO manual_job_entries (id, user_id, title, company, created_at)
                VALUES ('m1', 'u1', 'Backend Engineer', 'Acme', CURRENT_TIMESTAMP)
                """
            )
        )

    def test_both_set_is_rejected(self, sqlite_url: str):
        upgrade_head(sqlite_url)
        engine = sync_engine_for(sqlite_url)
        try:
            with pytest.raises(IntegrityError):
                with engine.begin() as conn:
                    self._seed_user_and_manual_entry(conn)
                    _insert_job_match(
                        conn,
                        match_id="jm_both",
                        user_id="u1",
                        job_posting_id="does-not-need-to-exist-for-check",
                        manual_job_entry_id="m1",
                    )
        finally:
            engine.dispose()

    def test_neither_set_is_rejected(self, sqlite_url: str):
        upgrade_head(sqlite_url)
        engine = sync_engine_for(sqlite_url)
        try:
            with pytest.raises(IntegrityError):
                with engine.begin() as conn:
                    self._seed_user_and_manual_entry(conn)
                    _insert_job_match(
                        conn,
                        match_id="jm_neither",
                        user_id="u1",
                        job_posting_id=None,
                        manual_job_entry_id=None,
                    )
        finally:
            engine.dispose()


class TestDowngrade:
    def test_downgrade_drops_manual_job_entries_and_reverts_job_matches(self, sqlite_url: str):
        upgrade_head(sqlite_url)
        _downgrade_to(sqlite_url, REV_INTERVIEW_SCHEDULES)
        names = table_names(sqlite_url)
        assert "manual_job_entries" not in names
        cols = _columns(sqlite_url, "job_matches")
        assert "manual_job_entry_id" not in cols
        assert cols["job_posting_id"]["nullable"] is False

    def test_downgrade_fails_if_manual_entry_rows_exist(self, sqlite_url: str):
        """§10.3's data-safety note: downgrading after real manual entries exist
        must fail loudly (job_posting_id NOT NULL can't hold), not silently drop
        or corrupt data."""
        upgrade_head(sqlite_url)
        engine = sync_engine_for(sqlite_url)
        try:
            with engine.begin() as conn:
                conn.execute(
                    sa_text(
                        """
                        INSERT INTO users (
                            id, email, first_name, last_name, is_active, is_verified,
                            created_at, updated_at
                        )
                        VALUES (
                            'u1', 'manual-jobs-downgrade@example.com', 'Test', 'User', 1, 1,
                            CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                        )
                        """
                    )
                )
                conn.execute(
                    sa_text(
                        """
                        INSERT INTO manual_job_entries (id, user_id, title, company, created_at)
                        VALUES ('m1', 'u1', 'Backend Engineer', 'Acme', CURRENT_TIMESTAMP)
                        """
                    )
                )
                _insert_job_match(
                    conn,
                    match_id="jm1",
                    user_id="u1",
                    job_posting_id=None,
                    manual_job_entry_id="m1",
                )
        finally:
            engine.dispose()

        with pytest.raises(Exception):
            _downgrade_to(sqlite_url, REV_INTERVIEW_SCHEDULES)

    def test_full_downgrade_then_reupgrade_is_clean(self, sqlite_url: str):
        upgrade_head(sqlite_url)
        _downgrade_to(sqlite_url, REV_INTERVIEW_SCHEDULES)
        names_after_downgrade = table_names(sqlite_url)
        assert "manual_job_entries" not in names_after_downgrade

        upgrade_head(sqlite_url)
        names_after_reupgrade = table_names(sqlite_url)
        assert "manual_job_entries" in names_after_reupgrade
        cols = _columns(sqlite_url, "job_matches")
        assert cols["job_posting_id"]["nullable"] is True
        assert "manual_job_entry_id" in cols


def test_043_is_in_the_migration_chain_and_is_the_single_head(sqlite_url: str) -> None:
    """Named after 043 (this module's own migration), but after the admin-module
    merge (migration 044, a no-op fork-resolution) and the subsequent Module 3
    (045) / Module 4 (046) admin-permission migrations, the single head is now
    046, with 044 (and therefore 043) reachable as an ancestor. This test still
    confirms 043 (and 042) are reachable from the single head, just not the
    head itself anymore.
    """
    from alembic.script import ScriptDirectory

    upgrade_head(sqlite_url)
    script_dir = ScriptDirectory.from_config(alembic_config(sqlite_url))
    heads = script_dir.get_heads()
    assert len(heads) == 1
    assert heads[0] == REV_CURRENT_SINGLE_HEAD

    ancestor_revisions = {
        rev.revision for rev in script_dir.walk_revisions(base="base", head=heads)
    }
    assert REV_MERGE_ADMIN_AND_MODULE4_HEADS in ancestor_revisions
    assert REV_MANUAL_JOB_ENTRIES in ancestor_revisions
    assert REV_INTERVIEW_SCHEDULES in ancestor_revisions
