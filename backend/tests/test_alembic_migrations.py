"""Alembic / JSONB edge-case matrix (problems A–D)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import JSON, DateTime, String, Text, inspect, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.database import session as db_mod
from app.database.base import JsonDoc
from app.modules.enrichment.models import JobRecord
from tests.migration_helpers import (
    alembic_config,
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
    # Session implementation lives in database/session (storage/db shim removed).
    session_source = Path(db_mod.__file__).resolve()
    source = session_source.read_text(encoding="utf-8")
    assert "metadata.create_all" not in source
    assert "_migrate_schema" not in source
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
                    INSERT INTO jobs (
                        id, status, request_payload, dossier_payload, identifier_hashes,
                        created_at, updated_at
                    )
                    VALUES (
                        'job_t1', 'queued', '{}', '{}', '[]',
                        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    )
                    """
                )
            )
            row = conn.execute(text("SELECT status FROM jobs WHERE id = 'job_t1'")).fetchone()
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

    class LegacyAuditLog(LegacyBase):
        __tablename__ = "audit_logs"
        id: Mapped[str] = mapped_column(String(64), primary_key=True)
        event_type: Mapped[str] = mapped_column(String(64), nullable=False)
        identifier_hash: Mapped[str] = mapped_column(String(128), nullable=False)
        job_id: Mapped[str | None] = mapped_column(String(64))
        details: Mapped[dict] = mapped_column(JSON, nullable=False)
        created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    class LegacyDsarRequest(LegacyBase):
        __tablename__ = "dsar_requests"
        id: Mapped[str] = mapped_column(String(64), primary_key=True)
        identifier_hash: Mapped[str] = mapped_column(String(128), nullable=False)
        request_type: Mapped[str] = mapped_column(String(32), nullable=False)
        status: Mapped[str] = mapped_column(String(32), nullable=False)
        details: Mapped[dict] = mapped_column(JSON, nullable=False)
        created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
        completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    class LegacyPhotoCache(LegacyBase):
        __tablename__ = "photo_cache"
        slug_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
        slug: Mapped[str] = mapped_column(String(255), nullable=False)
        asset_key: Mapped[str] = mapped_column(String(512), nullable=False)
        asset_url: Mapped[str] = mapped_column(String(1024), nullable=False)
        extraction_method: Mapped[str] = mapped_column(String(64), nullable=False)
        content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
        uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
        expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    engine = sync_engine_for(sqlite_url)
    try:
        LegacyBase.metadata.create_all(engine)
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO jobs (id, status, request_payload, dossier_payload, created_at, updated_at)
                    VALUES (
                        'job_legacy', 'completed', '{"email":"a@b.com"}', '{"handles":[]}',
                        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    )
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
            row = conn.execute(text("SELECT id FROM jobs WHERE id = 'job_legacy'")).fetchone()
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


def test_036_037_038_are_in_the_migration_chain(sqlite_url: str) -> None:
    """Renumbered Module 3 migrations must chain onto the real head, not fork it (§5).

    Lighter-weight than the full idempotent-upgrade tests above: confirms the
    tables these three revisions create/alter exist after ``upgrade_head``,
    and confirms 036 is a genuine ancestor of the current head via Alembic's
    own ``ScriptDirectory`` API (not string-matching revision ids).
    """
    from alembic.script import ScriptDirectory

    upgrade_head(sqlite_url)
    names = table_names(sqlite_url)
    assert "question_attempts" in names
    assert "practice_audio_recordings" in names

    script_dir = ScriptDirectory.from_config(alembic_config(sqlite_url))
    heads = script_dir.get_heads()
    ancestor_revisions = {
        rev.revision for rev in script_dir.walk_revisions(base="base", head=heads)
    }
    assert "036_question_attempt_fk_and_personalization" in ancestor_revisions
    assert "037_question_recency_index" in ancestor_revisions
    assert "038_practice_audio_recordings_voice_tone" in ancestor_revisions


def test_migration_chain_has_single_head(sqlite_url: str) -> None:
    """Regression guard for the 033-035/036-038 renumbering collision (Module 4 §2)."""
    from alembic.script import ScriptDirectory

    script_dir = ScriptDirectory.from_config(alembic_config(sqlite_url))
    assert len(script_dir.get_heads()) == 1


def test_question_attempts_question_id_has_fk_constraint(sqlite_url: str) -> None:
    """§4.2 regression guard - the exact bug this plan fixes."""
    upgrade_head(sqlite_url)
    engine = sync_engine_for(sqlite_url)
    try:
        with engine.connect() as conn:
            fks = inspect(conn).get_foreign_keys("question_attempts")
    finally:
        engine.dispose()
    assert any(fk["referred_table"] == "interview_questions" for fk in fks)


def test_interview_questions_has_personalization_columns(sqlite_url: str) -> None:
    upgrade_head(sqlite_url)
    engine = sync_engine_for(sqlite_url)
    try:
        with engine.connect() as conn:
            columns = {c["name"] for c in inspect(conn).get_columns("interview_questions")}
    finally:
        engine.dispose()
    assert "personalized_for_user_id" in columns
    assert "generation_context" in columns
