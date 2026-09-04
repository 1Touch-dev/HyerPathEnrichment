"""Add job_matches table for scored candidate-job pairings.

Revision ID: 021_job_matches
Revises: 020_candidate_job_preferences
Create Date: 2026-08-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "021_job_matches"
down_revision: str | Sequence[str] | None = "020_candidate_job_preferences"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    uuid_type = postgresql.UUID(as_uuid=True) if dialect == "postgresql" else sa.String(36)
    jsonb_type = postgresql.JSONB() if dialect == "postgresql" else sa.JSON()

    op.create_table(
        "job_matches",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column(
            "user_id", uuid_type, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "job_posting_id",
            uuid_type,
            sa.ForeignKey("job_postings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("similarity_score", sa.Float(), nullable=False),  # raw cosine similarity, 0.0-1.0
        sa.Column(
            "rule_score", sa.Float(), nullable=False
        ),  # salary/location/remote filter score, 0.0-1.0
        sa.Column("overall_score", sa.Float(), nullable=False),  # weighted composite, 0-100
        sa.Column("score_breakdown", jsonb_type, nullable=False, server_default="{}"),
        sa.Column(
            "explanation", sa.Text(), nullable=True
        ),  # LLM-generated "why this matches", nullable until generated
        sa.Column("explanation_generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("viewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "feedback", sa.String(10), nullable=True
        ),  # "up"|"down"|null — v2 hook, Decision 2
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_job_matches_user_id", "job_matches", ["user_id"])
    op.create_index("ix_job_matches_job_posting_id", "job_matches", ["job_posting_id"])
    op.create_index("ix_job_matches_overall_score", "job_matches", ["overall_score"])
    op.create_index(
        "ix_job_matches_user_posting", "job_matches", ["user_id", "job_posting_id"], unique=True
    )


def downgrade() -> None:
    op.drop_index("ix_job_matches_user_posting", table_name="job_matches")
    op.drop_index("ix_job_matches_overall_score", table_name="job_matches")
    op.drop_index("ix_job_matches_job_posting_id", table_name="job_matches")
    op.drop_index("ix_job_matches_user_id", table_name="job_matches")
    op.drop_table("job_matches")
