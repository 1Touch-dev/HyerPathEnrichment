"""Helpers for Alembic migration tests."""

from __future__ import annotations

import os
from pathlib import Path

from alembic import command
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine

from app.database.session import BASELINE_REVISION, alembic_config, legacy_pre_alembic, run_migrations


def postgres_test_url() -> str | None:
    return os.environ.get("TEST_DATABASE_URL") or None


def to_sync_url(url: str) -> str:
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
    if url.startswith("sqlite+aiosqlite://"):
        return url.replace("sqlite+aiosqlite://", "sqlite://", 1)
    return url


def sync_engine_for(url: str) -> Engine:
    return create_engine(to_sync_url(url))


def upgrade_head(url: str, *, stamp_if_legacy: bool = True) -> None:
    run_migrations(url, stamp_if_legacy=stamp_if_legacy)


def stamp_baseline(url: str) -> None:
    command.stamp(alembic_config(url), BASELINE_REVISION)


def downgrade_base(url: str) -> None:
    command.downgrade(alembic_config(url), "base")


def table_names(url: str) -> set[str]:
    engine = sync_engine_for(url)
    try:
        with engine.connect() as conn:
            return set(inspect(conn).get_table_names())
    finally:
        engine.dispose()


def column_udt(url: str, table: str, column: str) -> str | None:
    """Postgres udt_name for a column; SQLite returns a best-effort type string."""
    engine = sync_engine_for(url)
    try:
        with engine.connect() as conn:
            if conn.dialect.name == "postgresql":
                row = conn.execute(
                    text(
                        """
                        SELECT udt_name
                        FROM information_schema.columns
                        WHERE table_schema = 'public'
                          AND table_name = :table
                          AND column_name = :column
                        """
                    ),
                    {"table": table, "column": column},
                ).fetchone()
                return row[0] if row else None
            cols = {c["name"]: c for c in inspect(conn).get_columns(table)}
            col = cols.get(column)
            if col is None:
                return None
            col_type = col["type"]
            return type(col_type).__name__.lower()
    finally:
        engine.dispose()


def drop_all_user_tables(url: str) -> None:
    """Wipe schema objects so migration tests start clean (Postgres + SQLite)."""
    engine = sync_engine_for(url)
    try:
        with engine.begin() as conn:
            if conn.dialect.name == "postgresql":
                conn.execute(text("DROP SCHEMA public CASCADE"))
                conn.execute(text("CREATE SCHEMA public"))
            else:
                # SQLite: drop every table including alembic_version
                rows = conn.execute(
                    text("SELECT name FROM sqlite_master WHERE type='table'")
                ).fetchall()
                for (name,) in rows:
                    if name.startswith("sqlite_"):
                        continue
                    conn.execute(text(f'DROP TABLE IF EXISTS "{name}"'))
    finally:
        engine.dispose()


def sqlite_file_url(path: Path) -> str:
    return f"sqlite+aiosqlite:///{path.as_posix()}"


# Re-export for tests
__all__ = [
    "BASELINE_REVISION",
    "alembic_config",
    "column_udt",
    "downgrade_base",
    "drop_all_user_tables",
    "legacy_pre_alembic",
    "postgres_test_url",
    "sqlite_file_url",
    "stamp_baseline",
    "table_names",
    "upgrade_head",
]
