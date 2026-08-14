"""Add optional voice_tone_signals column to practice_audio_recordings.

Revision ID: 035_practice_audio_recordings_voice_tone
Revises: 034_question_recency_index
Create Date: 2026-08-14

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "035_practice_audio_recordings_voice_tone"
down_revision: str | Sequence[str] | None = "034_question_recency_index"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add nullable voice_tone_signals column, populated only when HUME_API_KEY is set.

    Null on every row when the feature is off - matches the repo's own
    fail-soft convention (LLM_MODE stub, R2 -> local fallback, Reacher
    `profiles: ["paid"]`) rather than a required column with a fake default.
    """
    bind = op.get_bind()
    dialect = bind.dialect.name
    jsonb_type = postgresql.JSONB() if dialect == "postgresql" else sa.JSON()

    op.add_column(
        "practice_audio_recordings",
        sa.Column("voice_tone_signals", jsonb_type, nullable=True),
    )


def downgrade() -> None:
    """Remove the voice_tone_signals column."""
    op.drop_column("practice_audio_recordings", "voice_tone_signals")
