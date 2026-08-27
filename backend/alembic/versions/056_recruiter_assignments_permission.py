"""Seed the recruiter_assignments:write permission gate for the new
recruiter-candidate assignment endpoints
(machine-2-parallel-tracks/08-recruiter-candidate-assignment.md).

The `recruiter_candidate_assignments` table itself already exists (created by
052_create_brands_and_candidate_assignments.py) -- this migration only adds
the new (resource, action) permission pair this chunk's router gates
assign/on-behalf-of-another-recruiter-unassign behind, and grants it to the
'team_owner' system role (seeded by 047_seed_system_roles.py) as the
"admin/team lead assigns a candidate to a recruiter" actor the spec describes.
Cross-dialect-safe UUID generation copied from
046_admin_seed_module4_permissions.py's insert mechanics (not
gen_random_uuid(), which is Postgres-only).

Revision ID: 056_recruiter_assignments_permission
Revises: 055_merge_tenancy_core_and_machine2_heads
Create Date: 2026-08-27
"""

from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa

from alembic import op

revision: str = "056_recruiter_assignments_permission"
down_revision: str | Sequence[str] | None = "055_merge_tenancy_core_and_machine2_heads"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RESOURCE = "recruiter_assignments"
ACTION = "write"


def upgrade() -> None:
    bind = op.get_bind()

    permissions_table = sa.table(
        "permissions",
        sa.column("id"),
        sa.column("resource"),
        sa.column("action"),
        sa.column("description"),
    )
    role_permissions_table = sa.table(
        "role_permissions", sa.column("role_id"), sa.column("permission_id")
    )

    existing = bind.execute(
        sa.text("SELECT id FROM permissions WHERE resource = :resource AND action = :action"),
        {"resource": RESOURCE, "action": ACTION},
    ).fetchone()
    if existing is not None:
        permission_id = existing[0]
    else:
        permission_id = str(uuid4())
        bind.execute(
            permissions_table.insert().values(
                id=permission_id,
                resource=RESOURCE,
                action=ACTION,
                description="Assign/unassign candidates to recruiters",
            )
        )

    team_owner_role = bind.execute(
        sa.text("SELECT id FROM roles WHERE name = :name"), {"name": "team_owner"}
    ).fetchone()
    if team_owner_role is not None:
        already_granted = bind.execute(
            sa.text(
                "SELECT 1 FROM role_permissions "
                "WHERE role_id = :role_id AND permission_id = :permission_id"
            ),
            {"role_id": team_owner_role[0], "permission_id": permission_id},
        ).fetchone()
        if already_granted is None:
            bind.execute(
                role_permissions_table.insert().values(
                    role_id=team_owner_role[0], permission_id=permission_id
                )
            )


def downgrade() -> None:
    bind = op.get_bind()

    row = bind.execute(
        sa.text("SELECT id FROM permissions WHERE resource = :resource AND action = :action"),
        {"resource": RESOURCE, "action": ACTION},
    ).fetchone()
    if row is None:
        return
    permission_id = row[0]

    bind.execute(
        sa.text("DELETE FROM role_permissions WHERE permission_id = :permission_id"),
        {"permission_id": permission_id},
    )
    bind.execute(
        sa.text("DELETE FROM permissions WHERE id = :permission_id"),
        {"permission_id": permission_id},
    )
