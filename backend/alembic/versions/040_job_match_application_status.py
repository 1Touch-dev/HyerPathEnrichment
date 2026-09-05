"""Add application_status enum column + status_updated_at to job_matches (Module 4, Module C).

Revision ID: 040_job_match_application_status
Revises: 039_job_match_apply_tracking
Create Date: 2026-08-20
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "040_job_match_application_status"
down_revision: str | Sequence[str] | None = "039_job_match_apply_tracking"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Enforced at the app layer (Pydantic Literal), NOT a DB-level CHECK/ENUM type —
# matches the existing convention already used for JobMatch.explanation_status
# and JobMatch.feedback (both plain String columns with app-layer validation
# only, per job_matching/models.py's own inline comments). A native Postgres
# ENUM type would also complicate the SQLite dev/test path, which this repo
# consistently avoids (see JsonDoc's JSONB-vs-JSON dialect branching for the
# same underlying reason).
_STATUS_DEFAULT = "new"


def upgrade() -> None:
    with op.batch_alter_table("job_matches") as batch_op:
        batch_op.add_column(
            sa.Column(
                "application_status", sa.String(20), nullable=False, server_default=_STATUS_DEFAULT
            )
        )
        batch_op.add_column(
            sa.Column("status_updated_at", sa.DateTime(timezone=True), nullable=True)
        )
    op.create_index(
        "ix_job_matches_user_application_status",
        "job_matches",
        ["user_id", "application_status"],
    )


def downgrade() -> None:
    op.drop_index("ix_job_matches_user_application_status", table_name="job_matches")
    with op.batch_alter_table("job_matches") as batch_op:
        batch_op.drop_column("status_updated_at")
        batch_op.drop_column("application_status")
