"""Merge job-board-cv and stabilization migration heads

Revision ID: 031_merge_jobcv_stab_heads
Revises: 026_add_document_mime_type, 030_outreach_messages
Create Date: 2026-08-11

"""

from collections.abc import Sequence

# NOTE: keep this <= 32 chars. alembic_version.version_num is VARCHAR(32) by
# default; the original descriptive id here
# ("031_merge_job_board_cv_and_stabilization_heads", 46 chars) silently
# "worked" on SQLite (TEXT storage class ignores declared length) but raised
# psycopg.errors.StringDataRightTruncation on Postgres, so `alembic upgrade
# head` against a real Postgres database always failed at this revision.
# Same class of bug already hit (and fixed) in 025_merge_job_match_heads.py.
revision: str = "031_merge_jobcv_stab_heads"
down_revision: str | Sequence[str] | None = (
    "026_add_document_mime_type",
    "030_outreach_messages",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """No-op merge: reconciles the job-board-cv migration chain (024_push_subscriptions
    -> ... -> 030_outreach_messages) with the previously merged job-matching/
    stabilization head (025_merge_job_match_heads, further extended by
    026_add_document_mime_type) back into a single head.
    """


def downgrade() -> None:
    """No-op: this is a merge point with no schema changes of its own."""
