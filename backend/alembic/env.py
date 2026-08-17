"""Alembic env — sync migrations via URL rewrite (safe inside a running event loop)."""

from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import create_engine, pool, text
from sqlalchemy.engine import Connection

from alembic import context

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.core.config import get_settings
from app.database.base import Base
from app.database.orm_registry import (
    AuditLog,
    DsarRecord,
    JobRecord,
    PhotoCacheRecord,
    SignalRecord,
    SuppressionRecord,
)

_ = (JobRecord, SuppressionRecord, AuditLog, DsarRecord, PhotoCacheRecord, SignalRecord)

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_database_url() -> str:
    url = config.get_main_option("sqlalchemy.url")
    if url:
        return url
    return get_settings().database_url


def to_sync_url(url: str) -> str:
    """Map async SQLAlchemy URLs to sync drivers for Alembic."""
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
    if url.startswith("sqlite+aiosqlite://"):
        return url.replace("sqlite+aiosqlite://", "sqlite://", 1)
    return url


def run_migrations_offline() -> None:
    context.configure(
        url=to_sync_url(get_database_url()),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def _ensure_wide_version_table(connection: Connection) -> None:
    """Pre-create alembic_version with version_num VARCHAR(255) on Postgres.

    Alembic auto-creates this table with VARCHAR(32) the first time a fresh
    (or freshly-stamped) database is migrated. Several of our merge-migration
    revision ids (e.g. "025_merge_job_matching_and_stabilization_heads") are
    longer than 32 chars, so the very first head-merge write fails with
    "value too long for type character varying(32)" on any brand-new
    Postgres. No-op if the table already exists.
    """
    if connection.dialect.name != "postgresql":
        return
    connection.execute(
        text(
            "CREATE TABLE IF NOT EXISTS alembic_version ("
            "version_num VARCHAR(255) NOT NULL, "
            "CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num))"
        )
    )
    connection.commit()


def do_run_migrations(connection: Connection) -> None:
    _ensure_wide_version_table(connection)
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(
        to_sync_url(get_database_url()),
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        do_run_migrations(connection)
    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
