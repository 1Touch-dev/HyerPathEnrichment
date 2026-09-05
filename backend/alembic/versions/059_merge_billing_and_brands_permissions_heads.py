"""Merge billing-stripe and brands-permissions migration heads.

Revision ID: 059_merge_billing_and_brands_permissions_heads
Revises: 056_billing_stripe_tables, 058_merge_brands_permissions_heads
Create Date: 2026-08-28

"""

from collections.abc import Sequence

revision: str = "059_merge_billing_and_brands_permissions_heads"
down_revision: str | Sequence[str] | None = (
    "056_billing_stripe_tables",
    "058_merge_brands_permissions_heads",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """No-op merge: reconciles the two independent chains that each forked
    from 055_merge_tenancy_core_and_machine2_heads — billing-stripe's
    user_subscriptions/stripe_webhook_events tables
    (056_billing_stripe_tables) and the Machine 1 six-track dispatch's
    brands-permissions merge (058_merge_brands_permissions_heads) — back
    into a single head.
    """


def downgrade() -> None:
    """No-op: this is a merge point with no schema changes of its own."""
