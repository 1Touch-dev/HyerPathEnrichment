"""Alembic / JSONB edge-case matrix (problems A–D)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import JSON, DateTime, String, Text, inspect, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.models import JobRecord, JsonDoc
from app.storage import db as db_mod
from tests.migration_helpers import (
    column_udt,
    downgrade_base,
    drop_all_user_tables,
    postgres_test_url,
    sqlite_file_url,
    sync_engine_for,
    table_names,
    upgrade_head,
)

DOC_COLUMNS = (
    ("jobs", "request_payload"),
    ("jobs", "dossier_payload"),
    ("jobs", "identifier_hashes"),
    ("audit_logs", "details"),
    ("dsar_requests", "details"),
)

REQUIRED_TABLES = {
    "jobs",
    "suppression_list",
    "audit_logs",
    "dsar_requests",
    "photo_cache",
    "alembic_version",
}


@pytest.fixture
def sqlite_url(tmp_path: Path) -> str:
    return sqlite_file_url(tmp_path / "migrate.db")


def test_no_migrate_schema_symbol() -> None:
    assert not hasattr(db_mod, "_migrate_schema")
    # Session implementation lives in database/session; storage/db is a shim.
    session_source = Path(db_mod.__file__).resolve().parents[1] / "database" / "session.py"
    source = session_source.read_text(encoding="utf-8")
    shim_source = Path(db_mod.__file__).read_text(encoding="utf-8")
    assert "metadata.create_all" not in source
    assert "metadata.create_all" not in shim_source
    assert "_migrate_schema" not in source
    assert "_migrate_schema" not in shim_source
    assert "command.upgrade" in source


def test_upgrade_head_sqlite_idempotent(sqlite_url: str) -> None:
    upgrade_head(sqlite_url)
    upgrade_head(sqlite_url)
    names = table_names(sqlite_url)
    assert REQUIRED_TABLES <= names

    engine = sync_engine_for(sqlite_url)
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO jobs (id, status, request_payload, dossier_payload, identifier_hashes)
                    VALUES ('job_t1', 'queued', '{}', '{}', '[]')
                    """
                )
            )
            row = conn.execute(
                text("SELECT status FROM jobs WHERE id = 'job_t1'")
            ).fetchone()
            assert row is not None
            assert row[0] == "queued"
    finally:
        engine.dispose()


def test_upgrade_downgrade_upgrade_sqlite(sqlite_url: str) -> None:
    upgrade_head(sqlite_url)
    assert "jobs" in table_names(sqlite_url)
    downgrade_base(sqlite_url)
    assert "jobs" not in table_names(sqlite_url)
    upgrade_head(sqlite_url)
    assert REQUIRED_TABLES <= table_names(sqlite_url)


def test_legacy_pre_alembic_bootstrap_sqlite(sqlite_url: str) -> None:
    """Simulate create_all era: tables exist, no alembic_version → stamp + upgrade."""

    class LegacyBase(DeclarativeBase):
        pass

    class LegacyJob(LegacyBase):
        __tablename__ = "jobs"
        id: Mapped[str] = mapped_column(String(64), primary_key=True)
        status: Mapped[str] = mapped_column(String(32), nullable=False)
        request_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
        dossier_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
        created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
        updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    class LegacySuppression(LegacyBase):
        __tablename__ = "suppression_list"
        identifier_hash: Mapped[str] = mapped_column(String(128), primary_key=True)
        reason: Mapped[str] = mapped_column(Text, nullable=False)
        created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    engine = sync_engine_for(sqlite_url)
    try:
        LegacyBase.metadata.create_all(engine)
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO jobs (id, status, request_payload, dossier_payload)
                    VALUES ('job_legacy', 'completed', '{"email":"a@b.com"}', '{"handles":[]}')
                    """
                )
            )
            assert "alembic_version" not in inspect(conn).get_table_names()
    finally:
        engine.dispose()

    upgrade_head(sqlite_url, stamp_if_legacy=True)
    names = table_names(sqlite_url)
    assert "alembic_version" in names

    engine = sync_engine_for(sqlite_url)
    try:
        with engine.connect() as conn:
            cols = {c["name"] for c in inspect(conn).get_columns("jobs")}
            assert "identifier_hashes" in cols
            row = conn.execute(
                text("SELECT id FROM jobs WHERE id = 'job_legacy'")
            ).fetchone()
            assert row is not None
    finally:
        engine.dispose()


@pytest.mark.postgres
def test_upgrade_head_postgres_jsonb() -> None:
    url = postgres_test_url()
    if not url:
        pytest.skip("TEST_DATABASE_URL not set")
    drop_all_user_tables(url)
    upgrade_head(url)
    upgrade_head(url)
    assert REQUIRED_TABLES <= table_names(url)
    for table, column in DOC_COLUMNS:
        assert column_udt(url, table, column) == "jsonb", f"{table}.{column}"


@pytest.mark.postgres
def test_legacy_pre_alembic_bootstrap_postgres() -> None:
    url = postgres_test_url()
    if not url:
        pytest.skip("TEST_DATABASE_URL not set")
    drop_all_user_tables(url)

    engine = sync_engine_for(url)
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE jobs (
                        id VARCHAR(64) PRIMARY KEY,
                        status VARCHAR(32) NOT NULL,
                        request_payload JSON NOT NULL,
                        dossier_payload JSON NOT NULL,
                        created_at TIMESTAMPTZ,
                        updated_at TIMESTAMPTZ
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    INSERT INTO jobs (id, status, request_payload, dossier_payload)
                    VALUES ('job_legacy', 'completed', '{"email":"a@b.com"}'::json, '{}'::json)
                    """
                )
            )
            for stmt in (
                """
                CREATE TABLE audit_logs (
                    id VARCHAR(64) PRIMARY KEY,
                    event_type VARCHAR(64) NOT NULL,
                    identifier_hash VARCHAR(128) NOT NULL,
                    job_id VARCHAR(64),
                    details JSON NOT NULL,
                    created_at TIMESTAMPTZ
                )
                """,
                """
                CREATE TABLE dsar_requests (
                    id VARCHAR(64) PRIMARY KEY,
                    identifier_hash VARCHAR(128) NOT NULL,
                    request_type VARCHAR(32) NOT NULL,
                    status VARCHAR(32) NOT NULL,
                    details JSON NOT NULL,
                    created_at TIMESTAMPTZ,
                    completed_at TIMESTAMPTZ
                )
                """,
                """
                CREATE TABLE suppression_list (
                    identifier_hash VARCHAR(128) PRIMARY KEY,
                    reason TEXT NOT NULL,
                    created_at TIMESTAMPTZ
                )
                """,
                """
                CREATE TABLE photo_cache (
                    slug_hash VARCHAR(64) PRIMARY KEY,
                    slug VARCHAR(255) NOT NULL,
                    asset_key VARCHAR(512) NOT NULL,
                    asset_url VARCHAR(1024) NOT NULL,
                    extraction_method VARCHAR(64) NOT NULL,
                    content_hash VARCHAR(64) NOT NULL,
                    uploaded_at TIMESTAMPTZ,
                    expires_at TIMESTAMPTZ
                )
                """,
            ):
                conn.execute(text(stmt))
    finally:
        engine.dispose()

    upgrade_head(url, stamp_if_legacy=True)
    assert "alembic_version" in table_names(url)
    for table, column in DOC_COLUMNS:
        assert column_udt(url, table, column) == "jsonb", f"{table}.{column}"

    engine = sync_engine_for(url)
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT request_payload->>'email' FROM jobs WHERE id = 'job_legacy'")
            ).fetchone()
            assert row is not None
            assert row[0] == "a@b.com"
    finally:
        engine.dispose()


@pytest.mark.postgres
def test_mixed_identifier_hashes_already_jsonb() -> None:
    url = postgres_test_url()
    if not url:
        pytest.skip("TEST_DATABASE_URL not set")
    drop_all_user_tables(url)

    engine = sync_engine_for(url)
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE jobs (
                        id VARCHAR(64) PRIMARY KEY,
                        status VARCHAR(32) NOT NULL,
                        request_payload JSON NOT NULL,
                        dossier_payload JSON NOT NULL,
                        identifier_hashes JSONB NOT NULL DEFAULT '[]'::jsonb,
                        created_at TIMESTAMPTZ,
                        updated_at TIMESTAMPTZ
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    INSERT INTO jobs (id, status, request_payload, dossier_payload, identifier_hashes)
                    VALUES (
                        'job_mix', 'queued', '{"x": true}'::json, '{}'::json,
                        '["abc"]'::jsonb
                    )
                    """
                )
            )
            for stmt in (
                """
                CREATE TABLE audit_logs (
                    id VARCHAR(64) PRIMARY KEY,
                    event_type VARCHAR(64) NOT NULL,
                    identifier_hash VARCHAR(128) NOT NULL,
                    job_id VARCHAR(64),
                    details JSON NOT NULL,
                    created_at TIMESTAMPTZ
                )
                """,
                """
                CREATE TABLE dsar_requests (
                    id VARCHAR(64) PRIMARY KEY,
                    identifier_hash VARCHAR(128) NOT NULL,
                    request_type VARCHAR(32) NOT NULL,
                    status VARCHAR(32) NOT NULL,
                    details JSON NOT NULL,
                    created_at TIMESTAMPTZ,
                    completed_at TIMESTAMPTZ
                )
                """,
                """
                CREATE TABLE suppression_list (
                    identifier_hash VARCHAR(128) PRIMARY KEY,
                    reason TEXT NOT NULL,
                    created_at TIMESTAMPTZ
                )
                """,
                """
                CREATE TABLE photo_cache (
                    slug_hash VARCHAR(64) PRIMARY KEY,
                    slug VARCHAR(255) NOT NULL,
                    asset_key VARCHAR(512) NOT NULL,
                    asset_url VARCHAR(1024) NOT NULL,
                    extraction_method VARCHAR(64) NOT NULL,
                    content_hash VARCHAR(64) NOT NULL,
                    uploaded_at TIMESTAMPTZ,
                    expires_at TIMESTAMPTZ
                )
                """,
            ):
                conn.execute(text(stmt))
    finally:
        engine.dispose()

    upgrade_head(url, stamp_if_legacy=True)
    for table, column in DOC_COLUMNS:
        assert column_udt(url, table, column) == "jsonb", f"{table}.{column}"

    engine = sync_engine_for(url)
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT identifier_hashes->0 FROM jobs WHERE id = 'job_mix'")
            ).fetchone()
            assert row is not None
            assert row[0] == "abc"
    finally:
        engine.dispose()


def test_job_record_model_uses_jsondoc() -> None:
    assert type(JobRecord.__table__.c.request_payload.type) is type(JsonDoc)
    assert type(JobRecord.__table__.c.dossier_payload.type) is type(JsonDoc)
    assert type(JobRecord.__table__.c.identifier_hashes.type) is type(JsonDoc)
