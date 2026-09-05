"""Seed Phase 2 moderation permissions and grant to existing roles (Admin Module).

Revision ID: 041_admin_seed_phase2_permissions
Revises: 040_phase2_moderation_columns
Create Date: 2026-08-20
"""

from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa

from alembic import op

revision: str = "041_admin_seed_phase2_permissions"
down_revision: str | Sequence[str] | None = "040_phase2_moderation_columns"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RESOURCE_ACTIONS = [
    ("job_postings", "read"),
    ("job_postings", "moderate"),
    ("documents", "read"),
    ("documents", "moderate"),
    ("job_swipe", "read"),
    ("portfolio", "read"),
    ("portfolio", "moderate"),
    ("outreach", "read"),
    ("outreach", "moderate"),
    ("content_review", "read"),
    ("content_review", "decide"),
    ("questions", "read"),
    ("questions", "moderate"),
    ("practice_audio", "read"),
    ("practice_audio", "moderate"),
]

READ_ONLY_ACTIONS = [ra for ra in RESOURCE_ACTIONS if ra[1] == "read"]


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

    admin_role_id = bind.execute(
        sa.text("SELECT id FROM roles WHERE name = :name"), {"name": "admin"}
    ).scalar_one()
    support_role_id = bind.execute(
        sa.text("SELECT id FROM roles WHERE name = :name"), {"name": "support"}
    ).scalar_one()

    permission_ids: dict[tuple[str, str], str] = {}
    for resource, action in RESOURCE_ACTIONS:
        pid = str(uuid4())
        permission_ids[(resource, action)] = pid
        bind.execute(
            permissions_table.insert().values(
                id=pid, resource=resource, action=action, description=f"{action} on {resource}"
            )
        )

    for ra in RESOURCE_ACTIONS:
        bind.execute(
            role_permissions_table.insert().values(
                role_id=admin_role_id, permission_id=permission_ids[ra]
            )
        )

    for ra in READ_ONLY_ACTIONS:
        bind.execute(
            role_permissions_table.insert().values(
                role_id=support_role_id, permission_id=permission_ids[ra]
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
