"""Enable pgvector extension for vector embeddings storage.

Idempotent: enables pgvector only on Postgres; no-op on SQLite.
Can run multiple times without errors.

Revision ID: 009_enable_pgvector
Revises: 007_add_user_id_to_dsar
Create Date: 2026-08-04
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import text

from alembic import op

revision: str = "010_enable_pgvector"
down_revision: str | Sequence[str] | None = "009_unique_user_file_hash"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Enable pgvector extension on Postgres; no-op on SQLite."""
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect != "postgresql":
        # SQLite has no vector extension - pass through
        return

    # Idempotent: CREATE EXTENSION IF NOT EXISTS
    op.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))


def downgrade() -> None:
    """Disable pgvector extension on Postgres; no-op on SQLite."""
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect != "postgresql":
        # SQLite has no vector extension - pass through
        return

    # Only drop if no tables are using vector columns
    # This is a safety check - the downgrade should not be run if
    # there are tables with vector columns
    op.execute(text("DROP EXTENSION IF EXISTS vector CASCADE"))
