"""Seed the ("brands", "read")/("brands", "write") permissions used by
backend/app/modules/brands/router.py (mirrors 047_seed_system_roles.py's
insert-if-missing pattern). Granted to the existing team_owner (read+write)
and recruiter (read-only) system roles — brand management is presentation/
config-only (docs/adr/0019-tenancy-model.md); this migration never touches
brand_id as a data-isolation column.

Revision ID: 056_seed_brands_permissions
Revises: 055_merge_tenancy_core_and_machine2_heads
Create Date: 2026-08-27
"""

from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa

from alembic import op

revision: str = "056_seed_brands_permissions"
down_revision: str | Sequence[str] | None = "055_merge_tenancy_core_and_machine2_heads"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RESOURCE_ACTIONS = [
    ("brands", "read"),
    ("brands", "write"),
]

# team_owner/recruiter are seeded by 047_seed_system_roles.py. team_owner gets
# both; recruiter is read-only, matching its existing read-only "users" grant.
TEAM_OWNER_ACTIONS = [("brands", "read"), ("brands", "write")]
RECRUITER_ACTIONS = [("brands", "read")]


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

    permission_ids: dict[tuple[str, str], str] = {}
    for resource, action in RESOURCE_ACTIONS:
        row = bind.execute(
            sa.text("SELECT id FROM permissions WHERE resource = :resource AND action = :action"),
            {"resource": resource, "action": action},
        ).fetchone()
        if row is not None:
            permission_ids[(resource, action)] = row[0]
            continue
        pid = str(uuid4())
        permission_ids[(resource, action)] = pid
        bind.execute(
            permissions_table.insert().values(
                id=pid, resource=resource, action=action, description=f"{action} on {resource}"
            )
        )

    role_rows = bind.execute(
        sa.text("SELECT id, name FROM roles WHERE name IN ('team_owner', 'recruiter')")
    ).fetchall()
    role_ids = {row[1]: row[0] for row in role_rows}

    role_actions = {
        "team_owner": TEAM_OWNER_ACTIONS,
        "recruiter": RECRUITER_ACTIONS,
    }
    for role_name, actions in role_actions.items():
        role_id = role_ids.get(role_name)
        if role_id is None:
            # team_owner/recruiter may not exist yet if 047_seed_system_roles.py
            # hasn't run in this environment — skip rather than fail; the
            # permission rows themselves are still created above so a later
            # role-permission grant can attach them.
            continue
        for ra in actions:
            existing = bind.execute(
                sa.text(
                    "SELECT 1 FROM role_permissions WHERE role_id = :role_id "
                    "AND permission_id = :permission_id"
                ),
                {"role_id": role_id, "permission_id": permission_ids[ra]},
            ).fetchone()
            if existing is not None:
                continue
            bind.execute(
                role_permissions_table.insert().values(
                    role_id=role_id, permission_id=permission_ids[ra]
                )
            )


def downgrade() -> None:
    bind = op.get_bind()

    permission_ids: list[str] = []
    for resource, action in RESOURCE_ACTIONS:
        row = bind.execute(
            sa.text("SELECT id FROM permissions WHERE resource = :resource AND action = :action"),
            {"resource": resource, "action": action},
        ).fetchone()
        if row is not None:
            permission_ids.append(row[0])

    if permission_ids:
        placeholders = ", ".join(f":pid_{i}" for i in range(len(permission_ids)))
        params = {f"pid_{i}": pid for i, pid in enumerate(permission_ids)}
        bind.execute(
            sa.text(f"DELETE FROM role_permissions WHERE permission_id IN ({placeholders})"),
            params,
        )
        bind.execute(
            sa.text(f"DELETE FROM permissions WHERE id IN ({placeholders})"),
            params,
        )
