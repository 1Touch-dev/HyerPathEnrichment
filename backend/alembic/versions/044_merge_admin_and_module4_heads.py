"""Merge admin-module and module4 migration heads

Revision ID: 044_merge_admin_and_module4_heads
Revises: 041_admin_seed_phase2_permissions, 043_manual_job_entries
Create Date: 2026-08-21

"""

from collections.abc import Sequence

revision: str = "044_merge_admin_and_module4_heads"
down_revision: str | Sequence[str] | None = (
    "041_admin_seed_phase2_permissions",
    "043_manual_job_entries",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """No-op merge: reconciles the admin-module migration chain (033_admin_roles_permissions
    -> ... -> 041_admin_seed_phase2_permissions) with the module 3/4 migration chain
    (036_question_attempt_fk_and_personalization -> ... -> 043_manual_job_entries) — both
    forked from 032_portfolio_item_image_url — back into a single head.
    """


def downgrade() -> None:
    """No-op: this is a merge point with no schema changes of its own."""
