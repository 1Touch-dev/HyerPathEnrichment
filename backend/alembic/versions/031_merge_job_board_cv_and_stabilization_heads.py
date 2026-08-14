"""Merge job-board-cv and stabilization migration heads

Revision ID: 031_merge_job_board_cv_and_stabilization_heads
Revises: 025_merge_job_match_heads, 030_outreach_messages
Create Date: 2026-08-11

"""

from collections.abc import Sequence

revision: str = "031_merge_job_board_cv_and_stabilization_heads"
down_revision: str | Sequence[str] | None = (
    "025_merge_job_match_heads",
    "030_outreach_messages",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """No-op merge: reconciles the job-board-cv migration chain (024_push_subscriptions
    -> ... -> 030_outreach_messages) with the previously merged job-matching/
    stabilization head (025_merge_job_match_heads) back into
    a single head.
    """


def downgrade() -> None:
    """No-op: this is a merge point with no schema changes of its own."""
