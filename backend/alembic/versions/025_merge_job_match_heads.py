"""Merge job-matching and stabilization migration heads

Revision ID: 025_merge_job_match_heads
Revises: 019_rename_audit_log_metadata, 024_push_subscriptions
Create Date: 2026-08-11

"""

from collections.abc import Sequence

# NOTE: keep this <= 32 chars. alembic_version.version_num is VARCHAR(32) by
# default; the original descriptive id here ("025_merge_job_matching_and_
# stabilization_heads", 46 chars) silently "worked" on SQLite (TEXT storage
# class ignores declared length) but raised
# psycopg.errors.StringDataRightTruncation on Postgres, so `alembic upgrade
# head` against a real Postgres database always failed at this revision.
revision: str = "025_merge_job_match_heads"
down_revision: str | Sequence[str] | None = (
    "019_rename_audit_log_metadata",
    "024_push_subscriptions",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """No-op merge: reconciles the two independent migration chains that
    branched off ``017_practice_audio_recordings`` (job-matching feature
    migrations vs. the stabilization branch's attempt_metadata/audit_log
    fixes) back into a single head.
    """


def downgrade() -> None:
    """No-op: this is a merge point with no schema changes of its own."""
