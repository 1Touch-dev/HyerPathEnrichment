"""Add explanation retry state machine columns to job_matches.

Revision ID: 023_job_match_explanation_status
Revises: 022_webhook_url_preferences
Create Date: 2026-08-11
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "023_job_match_explanation_status"
down_revision: str | Sequence[str] | None = "022_webhook_url_preferences"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "job_matches",
        sa.Column(
            "explanation_status", sa.String(20), nullable=False, server_default="not_explained"
        ),  # "not_explained"|"processing"|"explained"|"failed" — enforced at app layer, not DB
    )
    op.add_column("job_matches", sa.Column("last_error", sa.Text(), nullable=True))
    op.add_column(
        "job_matches",
        sa.Column("is_error", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "job_matches",
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
    )

    # Backfill: rows that already carry an explanation predate this state machine
    # and were, by definition, successfully explained.
    connection = op.get_bind()
    connection.execute(
        sa.text(
            "UPDATE job_matches SET explanation_status = 'explained' WHERE explanation IS NOT NULL"
        )
    )


def downgrade() -> None:
    op.drop_column("job_matches", "retry_count")
    op.drop_column("job_matches", "is_error")
    op.drop_column("job_matches", "last_error")
    op.drop_column("job_matches", "explanation_status")
