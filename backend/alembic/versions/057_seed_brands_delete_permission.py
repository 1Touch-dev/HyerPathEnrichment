"""Seed the `("brands", "delete")` permission and grant it to `team_owner`.

`deactivation_router.py` (post-tenancy-features/03-org-offboarding-and-
deletion.md) gates both `/api/admin/brands/{id}/deactivate` and
`.../reactivate` behind `require_permission("brands", "delete")`, but no
prior migration seeds that (resource, action) pair. `user_has_permission`
(app/modules/admin/permissions.py) is fail-closed, so without this row every
non-superuser gets a permanent 403 regardless of role. `team_owner` is the
role that owns `brands:write` (per the BR track's migration) and manages
brands generally, so it should also be able to deactivate/reactivate them.

Insert-if-missing throughout (mirrors 047_seed_system_roles.py) so this is
safe to run against a database where `("brands", "delete")` might already
exist for some other reason, and so upgrade()/downgrade()/upgrade() round-
trips cleanly with no duplicate-row risk.

Revision ID: 057_seed_brands_delete_permission
Revises: 055_merge_tenancy_core_and_machine2_heads
Create Date: 2026-08-27
"""

from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa

from alembic import op

revision: str = "057_seed_brands_delete_permission"
down_revision: str | Sequence[str] | None = "055_merge_tenancy_core_and_machine2_heads"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RESOURCE = "brands"
ACTION = "delete"
GRANTED_TO_ROLE = "team_owner"


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

    permission_row = bind.execute(
        sa.text("SELECT id FROM permissions WHERE resource = :resource AND action = :action"),
        {"resource": RESOURCE, "action": ACTION},
    ).fetchone()
    if permission_row is not None:
        permission_id = permission_row[0]
    else:
        permission_id = str(uuid4())
        bind.execute(
            permissions_table.insert().values(
                id=permission_id,
                resource=RESOURCE,
                action=ACTION,
                description=f"{ACTION} on {RESOURCE}",
            )
        )

    role_row = bind.execute(
        sa.text("SELECT id FROM roles WHERE name = :name"), {"name": GRANTED_TO_ROLE}
    ).fetchone()
    if role_row is None:
        # team_owner is seeded by 047_seed_system_roles.py, which is an
        # ancestor of this migration's down_revision chain — this branch
        # should be unreachable in practice, but skip the grant rather than
        # raise if some future rebase ever drops that assumption.
        return
    role_id = role_row[0]

    existing_grant = bind.execute(
        sa.text(
            "SELECT 1 FROM role_permissions WHERE role_id = :role_id "
            "AND permission_id = :permission_id"
        ),
        {"role_id": role_id, "permission_id": permission_id},
    ).fetchone()
    if existing_grant is None:
        bind.execute(
            role_permissions_table.insert().values(role_id=role_id, permission_id=permission_id)
        )


def downgrade() -> None:
    bind = op.get_bind()

    permission_row = bind.execute(
        sa.text("SELECT id FROM permissions WHERE resource = :resource AND action = :action"),
        {"resource": RESOURCE, "action": ACTION},
    ).fetchone()
    if permission_row is None:
        return
    permission_id = permission_row[0]

    role_row = bind.execute(
        sa.text("SELECT id FROM roles WHERE name = :name"), {"name": GRANTED_TO_ROLE}
    ).fetchone()
    if role_row is not None:
        bind.execute(
            sa.text(
                "DELETE FROM role_permissions WHERE role_id = :role_id "
                "AND permission_id = :permission_id"
            ),
            {"role_id": role_row[0], "permission_id": permission_id},
        )

    # ("brands", "delete") is net-new and owned solely by this migration —
    # safe to delete outright once no role_permissions row references it.
    still_referenced = bind.execute(
        sa.text("SELECT 1 FROM role_permissions WHERE permission_id = :pid LIMIT 1"),
        {"pid": permission_id},
    ).fetchone()
    if still_referenced is None:
        bind.execute(
            sa.text("DELETE FROM permissions WHERE id = :pid"), {"pid": permission_id}
        )
