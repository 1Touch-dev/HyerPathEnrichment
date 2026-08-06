"""Add practice_sessions and question_attempts tables.

Tracks user practice sessions and individual question attempts for interview practice.

Revision ID: 013_practice_sessions
Revises: 014_document_embeddings
Create Date: 2026-08-06
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "013_practice_sessions"
down_revision: Union[str, Sequence[str], None] = "014_document_embeddings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add practice_sessions and question_attempts tables."""
    bind = op.get_bind()
    dialect = bind.dialect.name

    # Use UUID type for Postgres, String for SQLite
    uuid_type = postgresql.UUID() if dialect == "postgresql" else sa.String(36)
    json_type = postgresql.JSONB() if dialect == "postgresql" else sa.JSON()

    # Create practice_sessions table
    op.create_table(
        "practice_sessions",
        sa.Column("id", uuid_type, primary_key=True, nullable=False),
        sa.Column(
            "user_id",
            uuid_type,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("session_type", sa.String(50), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="in_progress",
        ),
        sa.Column("questions_attempted", sa.Integer, nullable=False, server_default="0"),
        sa.Column("questions_completed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("overall_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("session_metadata", json_type, nullable=False, server_default="{}"),
    )

    # Add CHECK constraints for practice_sessions
    op.create_check_constraint(
        "check_session_status",
        "practice_sessions",
        "status IN ('pending', 'in_progress', 'completed', 'failed', 'abandoned')",
    )
    op.create_check_constraint(
        "check_questions_count",
        "practice_sessions",
        "questions_attempted >= questions_completed",
    )
    op.create_check_constraint(
        "check_overall_score_range",
        "practice_sessions",
        "overall_score IS NULL OR (overall_score >= 0 AND overall_score <= 100)",
    )

    # Create indexes for practice_sessions
    op.create_index(
        "idx_sessions_user_status", "practice_sessions", ["user_id", "status"]
    )
    op.create_index("idx_sessions_started", "practice_sessions", ["started_at"])

    # Create question_attempts table
    op.create_table(
        "question_attempts",
        sa.Column("id", uuid_type, primary_key=True, nullable=False),
        sa.Column(
            "session_id",
            uuid_type,
            sa.ForeignKey("practice_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            uuid_type,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("question_id", uuid_type, nullable=True),
        sa.Column("response_type", sa.String(10), nullable=False),
        sa.Column("text_response", sa.Text, nullable=True),
        sa.Column("audio_recording_id", uuid_type, nullable=True),
        sa.Column("ai_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("score_breakdown", json_type, nullable=True),
        sa.Column("ai_feedback", sa.Text, nullable=True),
        sa.Column("time_taken_seconds", sa.Integer, nullable=True),
        sa.Column(
            "attempted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("attempt_metadata", json_type, nullable=True),
    )

    # Add CHECK constraint for question_attempts
    op.create_check_constraint(
        "check_response_type",
        "question_attempts",
        "response_type IN ('text', 'audio')",
    )

    # Create indexes for question_attempts
    op.create_index("idx_attempts_session", "question_attempts", ["session_id"])
    op.create_index("idx_attempts_user", "question_attempts", ["user_id"])


def downgrade() -> None:
    """Remove practice_sessions and question_attempts tables."""
    # Drop question_attempts first (has FK to practice_sessions)
    op.drop_index("idx_attempts_user", table_name="question_attempts")
    op.drop_index("idx_attempts_session", table_name="question_attempts")
    op.drop_constraint("check_response_type", "question_attempts", type_="check")
    op.drop_table("question_attempts")

    # Drop practice_sessions
    op.drop_index("idx_sessions_started", table_name="practice_sessions")
    op.drop_index("idx_sessions_user_status", table_name="practice_sessions")
    op.drop_constraint("check_overall_score_range", "practice_sessions", type_="check")
    op.drop_constraint("check_questions_count", "practice_sessions", type_="check")
    op.drop_constraint("check_session_status", "practice_sessions", type_="check")
    op.drop_table("practice_sessions")
