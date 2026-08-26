"""Create ai_action_audit_log table (AI-agent supervision/audit-oversight view)
and seed the `ai_supervision:read` permission.

See task-orchestration/machine-2-parallel-tracks/04-rbac-admin-platform.md's
"AI-agent supervision (audit/oversight view)" section for why this table has
no DB-level FK constraint on `related_id` (polymorphic loose reference to a
JobMatch/OutreachMessage id, or None for resume_tailoring).

Revision ID: 052_ai_action_audit_log
Revises: 051_merge_machine2_parallel_track_heads
Create Date: 2026-08-26
"""

from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "052_ai_action_audit_log"
down_revision: str | Sequence[str] | None = "051_merge_machine2_parallel_track_heads"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RESOURCE_ACTION = ("ai_supervision", "read")


def _uuid_type():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return postgresql.UUID(as_uuid=True)
    return sa.String(36)


def upgrade() -> None:
    bind = op.get_bind()
    uuid_type = _uuid_type()

    op.create_table(
        "ai_action_audit_log",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("action_type", sa.String(30), nullable=False),
        sa.Column(
            "candidate_user_id",
            uuid_type,
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "triggered_by_user_id",
            uuid_type,
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # Deliberately no sa.ForeignKey here: related_id is a polymorphic
        # loose reference (JobMatch.id / OutreachMessage.id / None), not a
        # single-table FK -- see module docstring above.
        sa.Column("related_id", uuid_type, nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_ai_action_audit_log_action_type", "ai_action_audit_log", ["action_type"]
    )
    op.create_index(
        "ix_ai_action_audit_log_candidate_user_id", "ai_action_audit_log", ["candidate_user_id"]
    )
    op.create_index(
        "ix_ai_action_audit_log_triggered_by_user_id",
        "ai_action_audit_log",
        ["triggered_by_user_id"],
    )
    op.create_index(
        "ix_ai_action_audit_log_created_at", "ai_action_audit_log", ["created_at"]
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

    resource, action = RESOURCE_ACTION
    permission_id = str(uuid4())
    bind.execute(
        permissions_table.insert().values(
            id=permission_id,
            resource=resource,
            action=action,
            description=f"{action} on {resource}",
        )
    )

    # Grant to the existing "admin" role (seeded in 038_admin_seed_roles_permissions).
    # Do not block on 04-rbac-admin-platform.md's own team_owner/recruiter roles
    # landing first -- those are being added concurrently by a sibling track and
    # may not exist yet at the time this migration runs.
    admin_role_id = bind.execute(
        sa.text("SELECT id FROM roles WHERE name = :name"), {"name": "admin"}
    ).scalar_one_or_none()
    if admin_role_id is not None:
        bind.execute(
            role_permissions_table.insert().values(
                role_id=admin_role_id, permission_id=permission_id
            )
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

    op.drop_index("ix_ai_action_audit_log_created_at", table_name="ai_action_audit_log")
    op.drop_index(
        "ix_ai_action_audit_log_triggered_by_user_id", table_name="ai_action_audit_log"
    )
    op.drop_index(
        "ix_ai_action_audit_log_candidate_user_id", table_name="ai_action_audit_log"
    )
    op.drop_index("ix_ai_action_audit_log_action_type", table_name="ai_action_audit_log")
    op.drop_table("ai_action_audit_log")
