"""Create user_subscriptions and stripe_webhook_events tables (Stripe billing core).

See task-orchestration/post-tenancy-features/01-billing-stripe-integration.md's
`backend/app/modules/billing/models.py` section -- this migration mirrors that
shape exactly (no `seats_included` column; billing is candidate-level, never a
Brand/org seat license).

Revision ID: 056_billing_stripe_tables
Revises: 055_merge_tenancy_core_and_machine2_heads
Create Date: 2026-08-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "056_billing_stripe_tables"
down_revision: str | Sequence[str] | None = "055_merge_tenancy_core_and_machine2_heads"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _uuid_type():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return postgresql.UUID(as_uuid=True)
    return sa.String(36)


def upgrade() -> None:
    uuid_type = _uuid_type()

    op.create_table(
        "user_subscriptions",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column(
            "user_id",
            uuid_type,
            sa.ForeignKey(
                "users.id", ondelete="CASCADE", name="fk_user_subscriptions_user_id_users"
            ),
            nullable=False,
            unique=True,
        ),
        sa.Column("stripe_customer_id", sa.String(255), nullable=False, unique=True),
        sa.Column("stripe_subscription_id", sa.String(255), nullable=True, unique=True),
        sa.Column("plan_tier", sa.String(32), nullable=False, server_default="free"),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    # unique=True columns above already create implicit unique indexes for
    # stripe_customer_id/stripe_subscription_id on both dialects; user_id's
    # index is separate from its unique constraint since it is also looked up
    # directly by get_subscription_for_user(db, user_id).
    op.create_index("ix_user_subscriptions_user_id", "user_subscriptions", ["user_id"])
    op.create_index("ix_user_subscriptions_status", "user_subscriptions", ["status"])

    op.create_table(
        "stripe_webhook_events",
        sa.Column("stripe_event_id", sa.String(255), primary_key=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("stripe_webhook_events")

    op.drop_index("ix_user_subscriptions_status", table_name="user_subscriptions")
    op.drop_index("ix_user_subscriptions_user_id", table_name="user_subscriptions")
    op.drop_table("user_subscriptions")
