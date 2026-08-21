"""Seed default roles and permissions (Admin Module).

Revision ID: 038_admin_seed_roles_permissions
Revises: 037_admin_impersonation_sessions
Create Date: 2026-08-19
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa

from alembic import op

revision: str = "038_admin_seed_roles_permissions"
down_revision: str | Sequence[str] | None = "037_admin_impersonation_sessions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RESOURCE_ACTIONS = [
    ("users", "read"), ("users", "write"), ("users", "suspend"),
    ("roles", "read"), ("roles", "write"),
    ("audit_logs", "read"),
    ("feature_flags", "read"), ("feature_flags", "write"),
    ("queues", "read"), ("queues", "retry"),
    ("system_health", "read"),
    ("analytics", "read"),
    ("impersonation", "start"),
]

ROLES = [
    ("support", "Read-only + user suspend, no destructive or config access"),
    ("admin", "Full operational access, excludes role/permission management"),
]

ROLE_PERMISSIONS = {
    "support": [("users", "read"), ("users", "suspend"), ("audit_logs", "read"), ("system_health", "read")],
    "admin": [ra for ra in RESOURCE_ACTIONS if ra not in {("roles", "read"), ("roles", "write")}],
}


def upgrade() -> None:
    bind = op.get_bind()
    now = datetime.now(UTC)

    permissions_table = sa.table(
        "permissions",
        sa.column("id"),
        sa.column("resource"),
        sa.column("action"),
        sa.column("description"),
    )
    roles_table = sa.table(
        "roles",
        sa.column("id"),
        sa.column("name"),
        sa.column("description"),
        sa.column("is_system"),
        sa.column("created_at"),
        sa.column("updated_at"),
    )
    role_permissions_table = sa.table(
        "role_permissions", sa.column("role_id"), sa.column("permission_id")
    )

    permission_ids: dict[tuple[str, str], str] = {}
    for resource, action in RESOURCE_ACTIONS:
        pid = str(uuid4())
        permission_ids[(resource, action)] = pid
        bind.execute(
            permissions_table.insert().values(
                id=pid, resource=resource, action=action, description=f"{action} on {resource}"
            )
        )

    role_ids: dict[str, str] = {}
    for name, description in ROLES:
        rid = str(uuid4())
        role_ids[name] = rid
        bind.execute(
            roles_table.insert().values(
                id=rid,
                name=name,
                description=description,
                is_system=True,
                created_at=now,
                updated_at=now,
            )
        )

    for role_name, resource_actions in ROLE_PERMISSIONS.items():
        for ra in resource_actions:
            bind.execute(
                role_permissions_table.insert().values(
                    role_id=role_ids[role_name], permission_id=permission_ids[ra]
                )
            )


def downgrade() -> None:
    bind = op.get_bind()
    roles_table = sa.table("roles", sa.column("is_system"))
    bind.execute(sa.text("DELETE FROM role_permissions"))
    bind.execute(roles_table.delete().where(roles_table.c.is_system == True))  # noqa: E712
    bind.execute(sa.text("DELETE FROM permissions"))
