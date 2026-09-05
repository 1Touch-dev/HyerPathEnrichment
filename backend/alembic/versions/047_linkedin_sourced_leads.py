"""Create sourced_candidate_leads table (manual LinkedIn sourcing lead log) and
seed the `linkedin_sourcing:write` permission.

See task-orchestration/machine-2-parallel-tracks/12-linkedin-sourcing-intern-multilogin.md
for why this table only backs a manual data-entry form and never a scraper.

Revision ID: 047_linkedin_sourced_leads
Revises: 046_admin_seed_module4_permissions
Create Date: 2026-08-25
"""

from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "047_linkedin_sourced_leads"
down_revision: str | Sequence[str] | None = "046_admin_seed_module4_permissions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RESOURCE_ACTION = ("linkedin_sourcing", "write")


def _uuid_type():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return postgresql.UUID(as_uuid=True)
    return sa.String(36)


def upgrade() -> None:
    bind = op.get_bind()
    uuid_type = _uuid_type()

    op.create_table(
        "sourced_candidate_leads",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column(
            "sourced_by",
            uuid_type,
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("headline", sa.String(500), nullable=True),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("linkedin_profile_url", sa.String(512), nullable=False),
        sa.Column("target_role", sa.String(255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="new"),
        sa.Column(
            "reviewed_by",
            uuid_type,
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_sourced_candidate_leads_sourced_by", "sourced_candidate_leads", ["sourced_by"]
    )
    op.create_index("ix_sourced_candidate_leads_status", "sourced_candidate_leads", ["status"])

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
    # Do not block on 04-rbac-admin-platform.md's new team_owner/recruiter roles
    # landing first — those are being added concurrently by a sibling track and
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

    op.drop_index("ix_sourced_candidate_leads_status", table_name="sourced_candidate_leads")
    op.drop_index("ix_sourced_candidate_leads_sourced_by", table_name="sourced_candidate_leads")
    op.drop_table("sourced_candidate_leads")
