"""Add outreach_messages table for AI-drafted personalized outreach.

Revision ID: 030_outreach_messages
Revises: 029_job_swipe_actions
Create Date: 2026-08-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "030_outreach_messages"
down_revision: str | Sequence[str] | None = "029_job_swipe_actions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    uuid_type = postgresql.UUID(as_uuid=True) if dialect == "postgresql" else sa.String(36)
    jsonb_type = postgresql.JSONB() if dialect == "postgresql" else sa.JSON()

    op.create_table(
        "outreach_messages",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column(
            "user_id", uuid_type, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "job_match_id",
            uuid_type,
            sa.ForeignKey("job_matches.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "recipient_role_title", sa.String(255), nullable=True
        ),  # e.g. "Hiring Manager" — public title only
        sa.Column("company_name", sa.String(255), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "company_context_used", jsonb_type, nullable=False, server_default="{}"
        ),  # Perplexity result snapshot
        sa.Column(
            "status", sa.String(20), nullable=False, server_default="draft"
        ),  # "draft"|"sent"|"discarded"
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_outreach_messages_user_id", "outreach_messages", ["user_id"])
    op.create_index("ix_outreach_messages_status", "outreach_messages", ["status"])


def downgrade() -> None:
    op.drop_index("ix_outreach_messages_status", table_name="outreach_messages")
    op.drop_index("ix_outreach_messages_user_id", table_name="outreach_messages")
    op.drop_table("outreach_messages")
