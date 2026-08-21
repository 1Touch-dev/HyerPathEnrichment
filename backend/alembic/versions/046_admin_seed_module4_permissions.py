"""Add Module 4 admin-moderation columns and seed Module 4 admin permissions
(applications, interview_schedules, manual_job_entries).

Revision ID: 046_admin_seed_module4_permissions
Revises: 045_admin_module3_moderation_columns
Create Date: 2026-08-21
"""

from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "046_admin_seed_module4_permissions"
down_revision: str | Sequence[str] | None = "045_admin_module3_moderation_columns"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RESOURCE_ACTIONS = [
    ("applications", "read"),
    ("interview_schedules", "read"),
    ("interview_schedules", "moderate"),
    ("manual_job_entries", "read"),
    ("manual_job_entries", "moderate"),
]

READ_ONLY_ACTIONS = [ra for ra in RESOURCE_ACTIONS if ra[1] == "read"]


def _uuid_type():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return postgresql.UUID(as_uuid=True)
    return sa.String(36)


def upgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"
    uuid_type = _uuid_type()

    # SQLite has no native ALTER TABLE ADD CONSTRAINT/ADD FOREIGN KEY support —
    # batch mode (recreate-table) is required there for the admin_cancelled_by
    # FK, matching the existing pattern in 040_phase2_moderation_columns.py.
    # Postgres supports these ALTERs directly.
    if is_sqlite:
        with op.batch_alter_table("interview_schedules", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column("admin_cancelled_at", sa.DateTime(timezone=True), nullable=True)
            )
            batch_op.add_column(sa.Column("admin_cancelled_by", uuid_type, nullable=True))
            batch_op.create_foreign_key(
                "fk_interview_schedules_admin_cancelled_by",
                "users",
                ["admin_cancelled_by"],
                ["id"],
                ondelete="SET NULL",
            )
    else:
        op.add_column(
            "interview_schedules",
            sa.Column("admin_cancelled_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.add_column(
            "interview_schedules", sa.Column("admin_cancelled_by", uuid_type, nullable=True)
        )
        op.create_foreign_key(
            "fk_interview_schedules_admin_cancelled_by",
            "interview_schedules",
            "users",
            ["admin_cancelled_by"],
            ["id"],
            ondelete="SET NULL",
        )

    op.add_column(
        "manual_job_entries", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True)
    )

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
    is_sqlite = bind.dialect.name == "sqlite"

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

    op.drop_column("manual_job_entries", "deleted_at")

    if is_sqlite:
        with op.batch_alter_table("interview_schedules", schema=None) as batch_op:
            batch_op.drop_constraint(
                "fk_interview_schedules_admin_cancelled_by", type_="foreignkey"
            )
            batch_op.drop_column("admin_cancelled_by")
            batch_op.drop_column("admin_cancelled_at")
    else:
        op.drop_constraint(
            "fk_interview_schedules_admin_cancelled_by",
            "interview_schedules",
            type_="foreignkey",
        )
        op.drop_column("interview_schedules", "admin_cancelled_by")
        op.drop_column("interview_schedules", "admin_cancelled_at")
