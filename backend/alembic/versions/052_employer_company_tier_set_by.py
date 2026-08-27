"""Add set_by column to employer_company_tiers (machine-2/03: LLM-based
company-tier classifier with recruiter-override preservation).

Revision ID: 052_employer_company_tier_set_by
Revises: 051_merge_machine2_parallel_track_heads
Create Date: 2026-08-26
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "052_employer_company_tier_set_by"
down_revision: str | Sequence[str] | None = "051_merge_machine2_parallel_track_heads"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # server_default="recruiter" (NOT "llm", which is the model's Python-side
    # default for brand-new rows) is deliberate: every row that already exists
    # in employer_company_tiers before this migration was necessarily set by a
    # recruiter (the manual PUT /company-tier endpoint was the only write path
    # before classify_company_tier existed), so backfilling them as
    # set_by="recruiter" is required correctness, not a style choice --
    # defaulting existing rows to "llm" would let a future classifier run
    # silently overwrite a recruiter's real historical judgment, which is
    # exactly the bug this whole feature exists to prevent.
    op.add_column(
        "employer_company_tiers",
        sa.Column("set_by", sa.String(20), nullable=False, server_default="recruiter"),
    )


def downgrade() -> None:
    op.drop_column("employer_company_tiers", "set_by")
