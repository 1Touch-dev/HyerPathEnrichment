"""Merge brands-permissions migration heads.

Revision ID: 058_merge_brands_permissions_heads
Revises: 056_recruiter_assignments_permission, 056_seed_brands_permissions, 057_seed_brands_delete_permission
Create Date: 2026-08-27

"""

from collections.abc import Sequence

revision: str = "058_merge_brands_permissions_heads"
down_revision: str | Sequence[str] | None = (
    "056_recruiter_assignments_permission",
    "056_seed_brands_permissions",
    "057_seed_brands_delete_permission",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """No-op merge: reconciles the three independent chains that each forked
    from 055_merge_tenancy_core_and_machine2_heads during the Machine 1
    six-track dispatch — BR's ("brands", "read"/"write") permission seed,
    RA's ("recruiter_assignments", "write") permission seed, and BD's
    ("brands", "delete") permission seed — back into a single head.
    """


def downgrade() -> None:
    """No-op: this is a merge point with no schema changes of its own."""
