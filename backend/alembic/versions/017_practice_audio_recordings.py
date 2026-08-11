"""Add practice audio recordings table

Revision ID: 017_practice_audio_recordings
Revises: 015_add_session_tracking, 016_interview_questions
Create Date: 2026-08-07

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "017_practice_audio_recordings"
down_revision: str | Sequence[str] | None = ("015_add_session_tracking", "016_interview_questions")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add practice_audio_recordings table."""
    bind = op.get_bind()
    dialect = bind.dialect.name

    # Use UUID type for Postgres, String for SQLite
    uuid_type = postgresql.UUID(as_uuid=True) if dialect == "postgresql" else sa.String(36)
    jsonb_type = postgresql.JSONB() if dialect == "postgresql" else sa.JSON()

    op.create_table(
        "practice_audio_recordings",
        sa.Column("id", uuid_type, primary_key=True, nullable=False),
        sa.Column(
            "user_id", uuid_type, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "practice_session_id",
            uuid_type,
            sa.ForeignKey("practice_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("storage_path", sa.String(512), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("duration_seconds", sa.Numeric(10, 2), nullable=True),
        sa.Column("audio_format", sa.String(20), nullable=False),
        sa.Column("transcription", sa.Text(), nullable=True),
        sa.Column(
            "transcription_status",
            sa.String(20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("analysis_data", jsonb_type, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "transcription_status IN ('pending', 'processing', 'completed', 'failed')",
            name="check_transcription_status",
        ),
        sa.CheckConstraint(
            "file_size_bytes > 0",
            name="check_file_size_positive",
        ),
    )

    # Create indexes
    op.create_index(
        "idx_audio_user_session",
        "practice_audio_recordings",
        ["user_id", "practice_session_id"],
    )
    op.create_index("idx_audio_expires", "practice_audio_recordings", ["expires_at"])
    op.create_index(
        "idx_audio_transcription_status",
        "practice_audio_recordings",
        ["transcription_status"],
    )


def downgrade() -> None:
    """Remove practice_audio_recordings table."""
    op.drop_index("idx_audio_transcription_status", table_name="practice_audio_recordings")
    op.drop_index("idx_audio_expires", table_name="practice_audio_recordings")
    op.drop_index("idx_audio_user_session", table_name="practice_audio_recordings")
    op.drop_table("practice_audio_recordings")
