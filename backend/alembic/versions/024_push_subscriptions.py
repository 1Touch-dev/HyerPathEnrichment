"""Add push_subscriptions table for browser push notification delivery.

Revision ID: 024_push_subscriptions
Revises: 023_job_match_explanation_status
Create Date: 2026-08-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "024_push_subscriptions"
down_revision: str | Sequence[str] | None = "023_job_match_explanation_status"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    uuid_type = postgresql.UUID(as_uuid=True) if dialect == "postgresql" else sa.String(36)

    op.create_table(
        "push_subscriptions",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column(
            "user_id", uuid_type, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("endpoint", sa.Text(), nullable=False),
        sa.Column("p256dh_key", sa.Text(), nullable=False),
        sa.Column("auth_key", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_push_subscriptions_user_id", "push_subscriptions", ["user_id"])
    op.create_index(
        "ix_push_subscriptions_endpoint", "push_subscriptions", ["endpoint"], unique=True
    )


def downgrade() -> None:
    op.drop_index("ix_push_subscriptions_endpoint", table_name="push_subscriptions")
    op.drop_index("ix_push_subscriptions_user_id", table_name="push_subscriptions")
    op.drop_table("push_subscriptions")
