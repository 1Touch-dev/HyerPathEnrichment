"""Schema-verification tests for 050_country_demand_intelligence.

Follows the pattern in test_job_matching_migrations.py / test_manual_jobs_migrations.py:
run against a real SQLite file via Alembic upgrade/downgrade (not create_all), then
inspect the resulting schema.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import inspect
from sqlalchemy import text as sa_text
from sqlalchemy.exc import IntegrityError

from alembic import command
from tests.migration_helpers import alembic_config, sqlite_file_url, sync_engine_for, table_names

REV_BEFORE = "047_seed_system_roles"
REV_THIS = "050_country_demand_intelligence"


@pytest.fixture
def sqlite_url(tmp_path: Path) -> str:
    return sqlite_file_url(tmp_path / "demand_intelligence_migrate.db")


def _upgrade_to(url: str, revision: str) -> None:
    command.upgrade(alembic_config(url), revision)


def _downgrade_to(url: str, revision: str) -> None:
    command.downgrade(alembic_config(url), revision)


def _columns(url: str, table: str) -> dict[str, dict]:
    engine = sync_engine_for(url)
    try:
        with engine.connect() as conn:
            return {c["name"]: c for c in inspect(conn).get_columns(table)}
    finally:
        engine.dispose()


class TestCountryDemandSnapshotsTableCreated:
    def test_table_exists(self, sqlite_url: str):
        _upgrade_to(sqlite_url, REV_THIS)
        assert "country_demand_snapshots" in table_names(sqlite_url)

    def test_columns(self, sqlite_url: str):
        _upgrade_to(sqlite_url, REV_THIS)
        cols = _columns(sqlite_url, "country_demand_snapshots")
        expected = {
            "id",
            "snapshot_date",
            "country_iso2",
            "role_bucket",
            "posting_count",
            "remote_posting_count",
            "avg_salary_min",
            "avg_salary_max",
            "created_at",
        }
        assert expected <= cols.keys()
        assert cols["country_iso2"]["nullable"] is False
        assert cols["role_bucket"]["nullable"] is False
        assert cols["avg_salary_min"]["nullable"] is True
        assert cols["avg_salary_max"]["nullable"] is True

    def test_unique_constraint_prevents_duplicate_snapshot_rows(self, sqlite_url: str):
        _upgrade_to(sqlite_url, REV_THIS)
        engine = sync_engine_for(sqlite_url)
        try:
            with engine.begin() as conn:
                conn.execute(
                    sa_text(
                        """
                        INSERT INTO country_demand_snapshots
                            (id, snapshot_date, country_iso2, role_bucket,
                             posting_count, remote_posting_count, created_at)
                        VALUES
                            ('s1', '2026-08-25', 'us', 'backend engineer', 10, 2,
                             CURRENT_TIMESTAMP)
                        """
                    )
                )
            with pytest.raises(IntegrityError):
                with engine.begin() as conn:
                    conn.execute(
                        sa_text(
                            """
                            INSERT INTO country_demand_snapshots
                                (id, snapshot_date, country_iso2, role_bucket,
                                 posting_count, remote_posting_count, created_at)
                            VALUES
                                ('s2', '2026-08-25', 'us', 'backend engineer', 99, 0,
                                 CURRENT_TIMESTAMP)
                            """
                        )
                    )
        finally:
            engine.dispose()


class TestJobPostingsCountryIso2Column:
    def test_column_added_nullable(self, sqlite_url: str):
        _upgrade_to(sqlite_url, REV_THIS)
        cols = _columns(sqlite_url, "job_postings")
        assert "country_iso2" in cols
        assert cols["country_iso2"]["nullable"] is True


class TestDowngrade:
    def test_downgrade_drops_new_table_and_column(self, sqlite_url: str):
        _upgrade_to(sqlite_url, REV_THIS)
        _downgrade_to(sqlite_url, REV_BEFORE)

        names = table_names(sqlite_url)
        assert "country_demand_snapshots" not in names

        cols = _columns(sqlite_url, "job_postings")
        assert "country_iso2" not in cols

    def test_full_downgrade_then_reupgrade_is_clean(self, sqlite_url: str):
        _upgrade_to(sqlite_url, REV_THIS)
        _downgrade_to(sqlite_url, REV_BEFORE)
        _upgrade_to(sqlite_url, REV_THIS)

        assert "country_demand_snapshots" in table_names(sqlite_url)
        cols = _columns(sqlite_url, "job_postings")
        assert "country_iso2" in cols
