"""Add converted_user_id/converted_at columns to sourced_candidate_leads.

See task-orchestration/machine-2-parallel-tracks/12-linkedin-sourcing-intern-multilogin.md's
"Qualification path: SourcedCandidateLead -> User" section: a lead is linked to
the real User row it converted into once that person completes the existing
CV-chat qualification flow. No new permission needed here -- the conversion
endpoint reuses the existing linkedin_sourcing:write permission seeded by
047_linkedin_sourced_leads.

Revision ID: 052_linkedin_lead_conversion
Revises: 051_merge_machine2_parallel_track_heads
Create Date: 2026-08-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "052_linkedin_lead_conversion"
down_revision: str | Sequence[str] | None = "051_merge_machine2_parallel_track_heads"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _uuid_type():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return postgresql.UUID(as_uuid=True)
    return sa.String(36)


def upgrade() -> None:
    uuid_type = _uuid_type()
    # Batch mode required here: SQLite cannot ALTER-add a column with an inline
    # FK constraint outside the copy-and-move batch strategy (same pattern
    # 036_question_attempt_fk_and_personalization.py already uses for the same
    # reason). Batch mode is a no-op passthrough to plain ALTER TABLE on
    # PostgreSQL, so this is safe for both dialects.
    with op.batch_alter_table("sourced_candidate_leads") as batch_op:
        batch_op.add_column(
            sa.Column(
                "converted_user_id",
                uuid_type,
                sa.ForeignKey(
                    "users.id",
                    ondelete="SET NULL",
                    name="fk_sourced_candidate_leads_converted_user_id",
                ),
                nullable=True,
            )
        )
        batch_op.add_column(sa.Column("converted_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("sourced_candidate_leads") as batch_op:
        batch_op.drop_column("converted_at")
        batch_op.drop_column("converted_user_id")
