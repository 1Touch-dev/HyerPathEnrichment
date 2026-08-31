"""Merge security-p1 permissions head with billing/brands-permissions head.

Revision ID: 060_merge_security_p1_and_billing_heads
Revises: 059_merge_billing_and_brands_permissions_heads, 052_security_p1_permissions
Create Date: 2026-08-31

"""

from collections.abc import Sequence

revision: str = "060_merge_security_p1_and_billing_heads"
down_revision: str | Sequence[str] | None = (
    "059_merge_billing_and_brands_permissions_heads",
    "052_security_p1_permissions",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """No-op merge: reconciles the P1 security permissions revision
    (052_security_p1_permissions, forked from 051) with the integrate
    billing/brands chain that ends at
    059_merge_billing_and_brands_permissions_heads.
    """


def downgrade() -> None:
    """No-op: this is a merge point with no schema changes of its own."""
