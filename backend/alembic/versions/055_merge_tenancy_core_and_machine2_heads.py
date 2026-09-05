"""Merge tenancy-core and machine-2-parallel-tracks migration heads.

Revision ID: 055_merge_tenancy_core_and_machine2_heads
Revises: 053_staff_invites, 054_linkedin_lead_conversion
Create Date: 2026-08-27

"""

from collections.abc import Sequence

revision: str = "055_merge_tenancy_core_and_machine2_heads"
down_revision: str | Sequence[str] | None = (
    "053_staff_invites",
    "054_linkedin_lead_conversion",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """No-op merge: reconciles the two independent chains that forked from
    051_merge_machine2_parallel_track_heads — Machine 1's tenancy-core chain
    (052_create_brands_and_candidate_assignments -> 053_staff_invites) and
    Machine 2's parallel-tracks chain (052_employer_company_tier_set_by ->
    053_ai_action_audit_log -> 054_linkedin_lead_conversion) — back into a
    single head.
    """


def downgrade() -> None:
    """No-op: this is a merge point with no schema changes of its own."""
