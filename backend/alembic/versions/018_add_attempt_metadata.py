"""Add attempt_metadata to question_attempts

Revision ID: 018_add_attempt_metadata
Revises: 017_practice_audio_recordings
Create Date: 2026-08-08

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "018_add_attempt_metadata"
down_revision: str | Sequence[str] | None = "017_practice_audio_recordings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add attempt_metadata column to question_attempts for feedback worker context."""
    bind = op.get_bind()
    dialect = bind.dialect.name
    jsonb_type = postgresql.JSONB() if dialect == "postgresql" else sa.JSON()

    op.add_column(
        "question_attempts",
        sa.Column("attempt_metadata", jsonb_type, nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    """Remove attempt_metadata column from question_attempts."""
    op.drop_column("question_attempts", "attempt_metadata")
