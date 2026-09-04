"""Add job_postings table for deduplicated scraped job listings.

Revision ID: 018_job_postings
Revises: 017_practice_audio_recordings
Create Date: 2026-08-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "018_job_postings"
down_revision: str | Sequence[str] | None = "017_practice_audio_recordings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    uuid_type = postgresql.UUID(as_uuid=True) if dialect == "postgresql" else sa.String(36)
    jsonb_type = postgresql.JSONB() if dialect == "postgresql" else sa.JSON()

    op.create_table(
        "job_postings",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("dedup_key", sa.String(64), nullable=False),  # sha256 hex digest
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("company", sa.String(255), nullable=False),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("remote", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "source", sa.String(50), nullable=False
        ),  # "linkedin"|"indeed"|"glassdoor"|"google"|"zip_recruiter"
        sa.Column("source_url", sa.String(2048), nullable=True),
        sa.Column("description_raw", sa.Text(), nullable=True),
        sa.Column("salary_min", sa.Integer(), nullable=True),
        sa.Column("salary_max", sa.Integer(), nullable=True),
        sa.Column("salary_currency", sa.String(10), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "sources_seen", jsonb_type, nullable=False, server_default="[]"
        ),  # list[str], union of boards it appeared on
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_job_postings_dedup_key", "job_postings", ["dedup_key"], unique=True)
    op.create_index("ix_job_postings_is_active", "job_postings", ["is_active"])
    op.create_index("ix_job_postings_last_seen_at", "job_postings", ["last_seen_at"])


def downgrade() -> None:
    op.drop_index("ix_job_postings_last_seen_at", table_name="job_postings")
    op.drop_index("ix_job_postings_is_active", table_name="job_postings")
    op.drop_index("ix_job_postings_dedup_key", table_name="job_postings")
    op.drop_table("job_postings")
