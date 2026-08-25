"""Seed team_owner/recruiter system roles for this platform's own internal
team (owner-level + recruiter-staff), plus the ("roles", "write") permission
gate for the new create-role/attach-permission endpoints.

Not wired to Organization/org_id — that table does not exist yet when this
track is dispatched (machine-2-parallel-tracks/04-rbac-admin-platform.md).

Revision ID: 047_seed_system_roles
Revises: 046_admin_seed_module4_permissions
Create Date: 2026-08-25
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa

from alembic import op

revision: str = "047_seed_system_roles"
down_revision: str | Sequence[str] | None = "046_admin_seed_module4_permissions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Every (resource, action) pair either role needs. Most already exist from
# earlier admin-module migrations (038_admin_seed_roles_permissions.py seeded
# users:read/write and roles:read/write; 041_admin_seed_phase2_permissions.py
# seeded outreach/documents/portfolio/job_postings:read, but only :moderate,
# never :write, for those four) — checked against the live migration history
# at write time, not assumed. upgrade() queries for each pair before
# inserting, so this list is safe to run against either state.
NEEDED_RESOURCE_ACTIONS = [
    ("users", "read"),
    ("users", "write"),
    ("outreach", "read"),
    ("outreach", "write"),
    ("documents", "read"),
    ("documents", "write"),
    ("portfolio", "read"),
    ("portfolio", "write"),
    ("job_postings", "read"),
    ("job_postings", "write"),
    ("roles", "read"),
    ("roles", "write"),
]

# Subset of NEEDED_RESOURCE_ACTIONS verified NOT to exist anywhere in the
# migration history prior to this one (038/041/046) — i.e. genuinely owned
# and created by this migration, as opposed to users:read/write and
# roles:read/write which 038 already seeded. downgrade() only ever considers
# deleting rows in this set (and only if no other role still references
# them), so it can never remove a pre-existing Permission row it merely
# referenced.
NEW_PERMISSIONS_OWNED_BY_THIS_MIGRATION = [
    ("outreach", "write"),
    ("documents", "write"),
    ("portfolio", "write"),
    ("job_postings", "write"),
]

ROLES = [
    (
        "team_owner",
        "Full read/write across users, outreach, documents, portfolio, "
        "job_postings, and roles — this platform's own internal owner-level "
        "operator role.",
    ),
    (
        "recruiter",
        "Read/write on outreach, documents, portfolio, job_postings; "
        "read-only on users; no roles access — this platform's own internal "
        "recruiter-staff role.",
    ),
]

TEAM_OWNER_PERMISSIONS = [
    ("users", "read"),
    ("users", "write"),
    ("outreach", "read"),
    ("outreach", "write"),
    ("documents", "read"),
    ("documents", "write"),
    ("portfolio", "read"),
    ("portfolio", "write"),
    ("job_postings", "read"),
    ("job_postings", "write"),
    ("roles", "read"),
    ("roles", "write"),
]

RECRUITER_PERMISSIONS = [
    ("users", "read"),
    ("outreach", "read"),
    ("outreach", "write"),
    ("documents", "read"),
    ("documents", "write"),
    ("portfolio", "read"),
    ("portfolio", "write"),
    ("job_postings", "read"),
    ("job_postings", "write"),
]

ROLE_PERMISSIONS = {
    "team_owner": TEAM_OWNER_PERMISSIONS,
    "recruiter": RECRUITER_PERMISSIONS,
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
    for resource, action in NEEDED_RESOURCE_ACTIONS:
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

    role_rows = bind.execute(
        sa.text("SELECT id FROM roles WHERE name IN ('team_owner', 'recruiter')")
    ).fetchall()
    role_ids = [row[0] for row in role_rows]

    if role_ids:
        placeholders = ", ".join(f":rid_{i}" for i in range(len(role_ids)))
        params = {f"rid_{i}": rid for i, rid in enumerate(role_ids)}
        bind.execute(
            sa.text(f"DELETE FROM role_permissions WHERE role_id IN ({placeholders})"), params
        )
        bind.execute(sa.text(f"DELETE FROM roles WHERE id IN ({placeholders})"), params)

    # Only ever remove Permission rows this migration itself created
    # (NEW_PERMISSIONS_OWNED_BY_THIS_MIGRATION), and only if no other role's
    # role_permissions row still references them — never a pre-existing pair
    # like users:read/write or roles:read/write that 038 already owns.
    for resource, action in NEW_PERMISSIONS_OWNED_BY_THIS_MIGRATION:
        row = bind.execute(
            sa.text("SELECT id FROM permissions WHERE resource = :resource AND action = :action"),
            {"resource": resource, "action": action},
        ).fetchone()
        if row is None:
            continue
        permission_id = row[0]
        still_referenced = bind.execute(
            sa.text("SELECT 1 FROM role_permissions WHERE permission_id = :pid LIMIT 1"),
            {"pid": permission_id},
        ).fetchone()
        if still_referenced is None:
            bind.execute(sa.text("DELETE FROM permissions WHERE id = :pid"), {"pid": permission_id})
