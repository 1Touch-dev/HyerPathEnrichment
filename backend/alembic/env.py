"""Alembic env — sync migrations via URL rewrite (safe inside a running event loop)."""

from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import create_engine, inspect, pool, text
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


# Alembic's built-in `alembic_version.version_num` column is VARCHAR(32)
# (see alembic/ddl/impl.py's `version_table_impl`, which hardcodes
# `String(32)` with no way to override the width via `context.configure()`
# — there is no `version_table_column_kwargs` or similar option in
# Alembic 1.19.1, the version pinned in pyproject.toml, confirmed by
# inspecting the installed package and the current Alembic docs). This
# repo has migration revision ids longer than 32 chars (see the NOTE in
# 025_merge_job_match_heads.py for one example that was caught;
# 031_merge_job_board_cv_and_stabilization_heads, at 46 chars, was not),
# which raises psycopg.errors.StringDataRightTruncation on Postgres once
# `alembic upgrade head` reaches such a revision. SQLite ignores declared
# VARCHAR length entirely, so this only bites on Postgres.
# `_VERSION_NUM_WIDTH` must stay >= the longest revision id ever used.
_VERSION_NUM_WIDTH = 255
_VERSION_TABLE = "alembic_version"


def _widen_version_table_if_needed(connection: Connection) -> None:
    """Ensure ``alembic_version.version_num`` is wide enough on Postgres.

    Runs before `context.run_migrations()` so it covers both:
    - Fresh databases: pre-creates the version table ourselves with a wide
      column. Alembic's own table creation uses `checkfirst=True`, so it
      will see this table already exists and leave it alone.
    - Existing databases with an already-narrow (VARCHAR(32)) version
      table: widens the column in place via `ALTER TABLE`.

    No-op on non-Postgres dialects (e.g. SQLite, which doesn't enforce
    VARCHAR length anyway) and a no-op if the column is already wide
    enough.
    """
    if connection.dialect.name != "postgresql":
        return

    inspector = inspect(connection)
    if not inspector.has_table(_VERSION_TABLE):
        connection.execute(
            text(
                f"CREATE TABLE IF NOT EXISTS {_VERSION_TABLE} ("
                f"version_num VARCHAR({_VERSION_NUM_WIDTH}) NOT NULL, "
                f"CONSTRAINT {_VERSION_TABLE}_pkc PRIMARY KEY (version_num)"
                f")"
            )
        )
        connection.commit()
        return

    current_length = connection.execute(
        text(
            "SELECT character_maximum_length FROM information_schema.columns "
            "WHERE table_name = :table_name AND column_name = 'version_num'"
        ),
        {"table_name": _VERSION_TABLE},
    ).scalar()
    if current_length is not None and current_length < _VERSION_NUM_WIDTH:
        connection.execute(
            text(
                f"ALTER TABLE {_VERSION_TABLE} ALTER COLUMN version_num "
                f"TYPE VARCHAR({_VERSION_NUM_WIDTH})"
            )
        )
        connection.commit()


def do_run_migrations(connection: Connection) -> None:
    _widen_version_table_if_needed(connection)
    # Widen's SELECTs (and any no-op path) leave SQLAlchemy 2 autobegin open.
    # Alembic then uses a SAVEPOINT; connection.__exit__ rolls back the outer
    # transaction and the upgrade never sticks on Postgres. Commit first so
    # begin_transaction() owns a real top-level transaction.
    connection.commit()
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
