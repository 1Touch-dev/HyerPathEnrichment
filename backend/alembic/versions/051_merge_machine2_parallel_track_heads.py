"""Merge machine-2 parallel-tracks migration heads.

Revision ID: 051_merge_machine2_parallel_track_heads
Revises: 048c_linkedin_send_tasks, 049_recruiter_action_mode_and_pending_actions, 050_country_demand_intelligence
Create Date: 2026-08-25

"""

from collections.abc import Sequence

revision: str = "051_merge_machine2_parallel_track_heads"
down_revision: str | Sequence[str] | None = (
    "048c_linkedin_send_tasks",
    "049_recruiter_action_mode_and_pending_actions",
    "050_country_demand_intelligence",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """No-op merge: reconciles the three independent machine-2-parallel-tracks
    migration chains that all forked from 046_admin_seed_module4_permissions —
    the 03->05->06 outreach/LinkedIn-send chain (048c_linkedin_send_tasks), the
    09 recruiter-action-mode chain (049_recruiter_action_mode_and_pending_actions),
    and the 04->02 rbac/country-demand chain (050_country_demand_intelligence) —
    back into a single head.
    """


def downgrade() -> None:
    """No-op: this is a merge point with no schema changes of its own."""
