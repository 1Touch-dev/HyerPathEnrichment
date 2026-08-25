"""Add recipient_email + suppression_checked_at to outreach_messages for
CAN-SPAM send compliance (machine-2/05).

Revision ID: 048b_outreach_recipient_and_canspam
Revises: 048_outreach_strategy_dimension
Create Date: 2026-08-25
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "048b_outreach_recipient_and_canspam"
down_revision: str | Sequence[str] | None = "048_outreach_strategy_dimension"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("outreach_messages", sa.Column("recipient_email", sa.String(320), nullable=True))
    op.add_column(
        "outreach_messages",
        sa.Column("suppression_checked_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("outreach_messages", "suppression_checked_at")
    op.drop_column("outreach_messages", "recipient_email")
