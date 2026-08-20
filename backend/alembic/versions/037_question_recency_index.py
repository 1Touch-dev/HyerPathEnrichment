"""Add composite index for the corrected question-recency exclusion query.

Revision ID: 037_question_recency_index
Revises: 036_question_attempt_fk_and_personalization
Create Date: 2026-08-14

"""

from collections.abc import Sequence

from alembic import op

revision: str = "037_question_recency_index"
down_revision: str | Sequence[str] | None = "036_question_attempt_fk_and_personalization"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add composite index used by question_selector.py's recency-exclusion query.

    question_attempts already has idx_attempts_user (user_id) from
    015_add_session_tracking; this composite index makes the corrected
    "exclude questions this user attempted in the last N days" query an
    index-only scan instead of a filter over every row for a heavy user,
    since idx_attempts_user alone does not include attempted_at or question_id.
    """
    op.create_index(
        "idx_attempts_user_question_recency",
        "question_attempts",
        ["user_id", "attempted_at", "question_id"],
    )


def downgrade() -> None:
    """Remove the composite recency index."""
    op.drop_index("idx_attempts_user_question_recency", table_name="question_attempts")
