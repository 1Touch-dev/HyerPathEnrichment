"""Create linkedin_send_batches and linkedin_send_tasks tables (Machine-2/06: manual
human-operated LinkedIn send queue plus an operator-triggered automated-batch mode
skeleton), add outreach_messages.recipient_linkedin_url, and seed the
`linkedin_tasks:operate` permission.

The automated-click mechanism itself is explicitly out of scope for this track (see
app/workers/tasks/linkedin_send_batch.py's module docstring) — this migration only
adds the data model and RBAC gate for the human-trigger + rate-limit boundary.

Revision ID: 048c_linkedin_send_tasks
Revises: 048b_outreach_recipient_and_canspam
Create Date: 2026-08-25
"""

from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "048c_linkedin_send_tasks"
down_revision: str | Sequence[str] | None = "048b_outreach_recipient_and_canspam"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RESOURCE_ACTION = ("linkedin_tasks", "operate")


def _uuid_type():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return postgresql.UUID(as_uuid=True)
    return sa.String(36)


def upgrade() -> None:
    bind = op.get_bind()
    uuid_type = _uuid_type()

    op.add_column(
        "outreach_messages",
        sa.Column("recipient_linkedin_url", sa.String(512), nullable=True),
    )

    op.create_table(
        "linkedin_send_batches",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column(
            "triggered_by",
            uuid_type,
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("multilogin_profile_id", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("max_sends_per_day", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_linkedin_send_batches_status", "linkedin_send_batches", ["status"])

    op.create_table(
        "linkedin_send_tasks",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column(
            "outreach_message_id",
            uuid_type,
            sa.ForeignKey("outreach_messages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "batch_id",
            uuid_type,
            sa.ForeignKey("linkedin_send_batches.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("linkedin_profile_url", sa.String(512), nullable=False),
        sa.Column("action_type", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column(
            "claimed_by",
            uuid_type,
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("outcome_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_linkedin_send_tasks_outreach_message_id",
        "linkedin_send_tasks",
        ["outreach_message_id"],
    )
    op.create_index("ix_linkedin_send_tasks_batch_id", "linkedin_send_tasks", ["batch_id"])
    op.create_index("ix_linkedin_send_tasks_status", "linkedin_send_tasks", ["status"])

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

    # Grant to the existing "admin" role (seeded in 038_admin_seed_roles_permissions),
    # same pattern as 047_linkedin_sourced_leads.py — do not block on other tracks'
    # concurrently-added roles.
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

    op.drop_index("ix_linkedin_send_tasks_status", table_name="linkedin_send_tasks")
    op.drop_index("ix_linkedin_send_tasks_batch_id", table_name="linkedin_send_tasks")
    op.drop_index("ix_linkedin_send_tasks_outreach_message_id", table_name="linkedin_send_tasks")
    op.drop_table("linkedin_send_tasks")

    op.drop_index("ix_linkedin_send_batches_status", table_name="linkedin_send_batches")
    op.drop_table("linkedin_send_batches")

    op.drop_column("outreach_messages", "recipient_linkedin_url")
