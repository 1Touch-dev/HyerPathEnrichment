"""Idempotent promote of document columns to JSONB (+ add missing cols).

On Postgres: add missing columns as JSONB; ALTER json → jsonb when needed.
On SQLite: add missing columns as JSON only (SQLite has no jsonb); type no-ops.

Safe for mixed legacy DBs where identifier_hashes may already be jsonb (from
the old hand _migrate_schema) while other columns remain json.

Revision ID: 002_promote_json_to_jsonb
Revises: 001_baseline_schema
Create Date: 2026-07-15
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import inspect, text

from alembic import op

revision: str = "002_promote_json_to_jsonb"
down_revision: str | Sequence[str] | None = "001_baseline_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (table, column, pg_default, sqlite_default_literal)
_DOC_COLUMNS: tuple[tuple[str, str, str, str], ...] = (
    ("jobs", "request_payload", "'{}'::jsonb", "{}"),
    ("jobs", "dossier_payload", "'{}'::jsonb", "{}"),
    ("jobs", "identifier_hashes", "'[]'::jsonb", "[]"),
    ("audit_logs", "details", "'{}'::jsonb", "{}"),
    ("dsar_requests", "details", "'{}'::jsonb", "{}"),
)


def _pg_column_udt(connection, table: str, column: str) -> str | None:
    row = connection.execute(
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


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    dialect = bind.dialect.name

    for table, column, pg_default, sqlite_default in _DOC_COLUMNS:
        if table not in tables:
            continue
        existing = {c["name"] for c in inspector.get_columns(table)}
        if column not in existing:
            if dialect == "postgresql":
                op.execute(
                    text(
                        f"ALTER TABLE {table} ADD COLUMN {column} JSONB NOT NULL "
                        f"DEFAULT {pg_default}"
                    )
                )
            else:
                # SQLite: JSON affinity via SQLAlchemy JSON type
                op.add_column(
                    table,
                    sa.Column(
                        column,
                        sa.JSON(),
                        nullable=False,
                        server_default=sqlite_default,
                    ),
                )
            # Refresh inspector after DDL
            inspector = inspect(bind)
            continue

        if dialect != "postgresql":
            continue

        udt = _pg_column_udt(bind, table, column)
        if udt == "json":
            op.execute(
                text(f"ALTER TABLE {table} ALTER COLUMN {column} TYPE jsonb USING {column}::jsonb")
            )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        # Do not drop columns on SQLite downgrade — 001 drop_table handles cleanup.
        return

    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    for table, column, _pg_default, _sqlite_default in _DOC_COLUMNS:
        if table not in tables:
            continue
        udt = _pg_column_udt(bind, table, column)
        if udt == "jsonb":
            op.execute(
                text(f"ALTER TABLE {table} ALTER COLUMN {column} TYPE json USING {column}::json")
            )
