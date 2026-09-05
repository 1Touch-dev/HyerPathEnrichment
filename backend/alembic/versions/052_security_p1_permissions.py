"""Seed recruiter_actions:write and grant to admin + recruiter roles.

Also grant linkedin_sourcing:write to recruiter (list now requires it).

Revision ID: 052_security_p1_permissions
Revises: 051_merge_machine2_parallel_track_heads
Create Date: 2026-08-26
"""

from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa

from alembic import op

revision: str = "052_security_p1_permissions"
down_revision: str | Sequence[str] | None = "051_merge_machine2_parallel_track_heads"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RESOURCE_ACTION = ("recruiter_actions", "write")
GRANT_TO_ROLES = ("admin", "recruiter")


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
        "role_permissions",
        sa.column("role_id"),
        sa.column("permission_id"),
    )

    resource, action = RESOURCE_ACTION
    existing = bind.execute(
        sa.text("SELECT id FROM permissions WHERE resource = :resource AND action = :action"),
        {"resource": resource, "action": action},
    ).scalar_one_or_none()
    if existing is None:
        permission_id = str(uuid4())
        bind.execute(
            permissions_table.insert().values(
                id=permission_id,
                resource=resource,
                action=action,
                description="Create apply/suggest actions on behalf of candidates",
            )
        )
    else:
        permission_id = existing

    for role_name in GRANT_TO_ROLES:
        role_id = bind.execute(
            sa.text("SELECT id FROM roles WHERE name = :name"), {"name": role_name}
        ).scalar_one_or_none()
        if role_id is None:
            continue
        already = bind.execute(
            sa.text("SELECT 1 FROM role_permissions WHERE role_id = :rid AND permission_id = :pid"),
            {"rid": role_id, "pid": permission_id},
        ).scalar_one_or_none()
        if already is None:
            bind.execute(
                role_permissions_table.insert().values(role_id=role_id, permission_id=permission_id)
            )

    li_perm = bind.execute(
        sa.text("SELECT id FROM permissions WHERE resource = :resource AND action = :action"),
        {"resource": "linkedin_sourcing", "action": "write"},
    ).scalar_one_or_none()
    recruiter_id = bind.execute(
        sa.text("SELECT id FROM roles WHERE name = :name"), {"name": "recruiter"}
    ).scalar_one_or_none()
    if li_perm is not None and recruiter_id is not None:
        already = bind.execute(
            sa.text("SELECT 1 FROM role_permissions WHERE role_id = :rid AND permission_id = :pid"),
            {"rid": recruiter_id, "pid": li_perm},
        ).scalar_one_or_none()
        if already is None:
            bind.execute(
                role_permissions_table.insert().values(role_id=recruiter_id, permission_id=li_perm)
            )


def downgrade() -> None:
    bind = op.get_bind()
    resource, action = RESOURCE_ACTION
    row = bind.execute(
        sa.text("SELECT id FROM permissions WHERE resource = :resource AND action = :action"),
        {"resource": resource, "action": action},
    ).fetchone()
    if row is not None:
        permission_id = row[0]
        bind.execute(
            sa.text("DELETE FROM role_permissions WHERE permission_id = :pid"),
            {"pid": permission_id},
        )
        bind.execute(
            sa.text("DELETE FROM permissions WHERE id = :pid"),
            {"pid": permission_id},
        )
