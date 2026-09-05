"""Add outreach strategy dimension (strategy, referral_context, role_type,
seniority) to outreach_messages, and the employer_company_tiers table for
manual company-tier classification (machine-2/03).

Revision ID: 048_outreach_strategy_dimension
Revises: 047_linkedin_sourced_leads
Create Date: 2026-08-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "048_outreach_strategy_dimension"
down_revision: str | Sequence[str] | None = "047_linkedin_sourced_leads"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _uuid_type():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return postgresql.UUID(as_uuid=True)
    return sa.String(36)


def upgrade() -> None:
    uuid_type = _uuid_type()
    op.add_column(
        "outreach_messages",
        sa.Column("strategy", sa.String(20), nullable=False, server_default="direct_pitch"),
    )
    op.create_index("ix_outreach_messages_strategy", "outreach_messages", ["strategy"])
    op.add_column("outreach_messages", sa.Column("referral_context", sa.Text(), nullable=True))
    op.add_column("outreach_messages", sa.Column("role_type", sa.String(20), nullable=True))
    op.add_column("outreach_messages", sa.Column("seniority", sa.String(20), nullable=True))

    op.create_table(
        "employer_company_tiers",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("company_name", sa.String(255), nullable=False),
        sa.Column("tier", sa.String(20), nullable=False),
        sa.Column("set_by_user_id", uuid_type, nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["set_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_name"),
    )
    op.create_index(
        "ix_employer_company_tiers_company_name", "employer_company_tiers", ["company_name"]
    )


def downgrade() -> None:
    op.drop_index("ix_employer_company_tiers_company_name", table_name="employer_company_tiers")
    op.drop_table("employer_company_tiers")

    op.drop_column("outreach_messages", "seniority")
    op.drop_column("outreach_messages", "role_type")
    op.drop_column("outreach_messages", "referral_context")
    op.drop_index("ix_outreach_messages_strategy", table_name="outreach_messages")
    op.drop_column("outreach_messages", "strategy")
