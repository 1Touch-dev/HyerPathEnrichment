"""Grant team_owner every existing Desk permission.

Revision ID: 061_team_owner_full_desk_grants
Revises: 060_merge_security_p1_and_billing_heads
Create Date: 2026-09-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "061_team_owner_full_desk_grants"
down_revision: str | Sequence[str] | None = "060_merge_security_p1_and_billing_heads"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TEAM_OWNER_ROLE = "team_owner"
GRANT_TRACKING_TABLE = "migration_061_team_owner_grants"

# Complete permission inventory present at the verified parent revision. Keep
# this explicit: Product Doors must not create permission slugs implicitly.
DESK_PERMISSIONS = (
    ("ai_supervision", "read"),
    ("analytics", "read"),
    ("applications", "read"),
    ("audit_logs", "read"),
    ("brands", "delete"),
    ("brands", "read"),
    ("brands", "write"),
    ("content_review", "decide"),
    ("content_review", "read"),
    ("documents", "moderate"),
    ("documents", "read"),
    ("documents", "write"),
    ("feature_flags", "read"),
    ("feature_flags", "write"),
    ("impersonation", "start"),
    ("interview_schedules", "moderate"),
    ("interview_schedules", "read"),
    ("job_postings", "moderate"),
    ("job_postings", "read"),
    ("job_postings", "write"),
    ("job_swipe", "read"),
    ("linkedin_sourcing", "write"),
    ("linkedin_tasks", "operate"),
    ("manual_job_entries", "moderate"),
    ("manual_job_entries", "read"),
    ("outreach", "moderate"),
    ("outreach", "read"),
    ("outreach", "write"),
    ("portfolio", "moderate"),
    ("portfolio", "read"),
    ("portfolio", "write"),
    ("practice_audio", "moderate"),
    ("practice_audio", "read"),
    ("questions", "moderate"),
    ("questions", "read"),
    ("queues", "read"),
    ("queues", "retry"),
    ("recruiter_actions", "write"),
    ("recruiter_assignments", "write"),
    ("roles", "read"),
    ("roles", "write"),
    ("system_health", "read"),
    ("users", "read"),
    ("users", "suspend"),
    ("users", "write"),
)


def _uuid_type() -> sa.types.TypeEngine:
    if op.get_bind().dialect.name == "postgresql":
        return postgresql.UUID(as_uuid=True)
    return sa.String(36)


def upgrade() -> None:
    bind = op.get_bind()

    role_id = bind.execute(
        sa.text("SELECT id FROM roles WHERE name = :name"),
        {"name": TEAM_OWNER_ROLE},
    ).scalar_one_or_none()
    if role_id is None:
        raise RuntimeError(
            "061_team_owner_full_desk_grants requires the team_owner role "
            "from 047_seed_system_roles"
        )

    permission_rows = bind.execute(
        sa.text("SELECT id, resource, action FROM permissions")
    ).fetchall()
    permission_ids = {(row[1], row[2]): row[0] for row in permission_rows}
    missing = sorted(set(DESK_PERMISSIONS) - permission_ids.keys())
    if missing:
        slugs = ", ".join(f"{resource}:{action}" for resource, action in missing)
        raise RuntimeError(
            "061_team_owner_full_desk_grants is missing expected permission rows: "
            f"{slugs}"
        )

    uuid_type = _uuid_type()
    op.create_table(
        GRANT_TRACKING_TABLE,
        sa.Column(
            "role_id",
            uuid_type,
            sa.ForeignKey("roles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "permission_id",
            uuid_type,
            sa.ForeignKey("permissions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("role_id", "permission_id"),
    )

    role_permissions = sa.table(
        "role_permissions",
        sa.column("role_id"),
        sa.column("permission_id"),
    )
    tracked_grants = sa.table(
        GRANT_TRACKING_TABLE,
        sa.column("role_id"),
        sa.column("permission_id"),
    )

    for permission in DESK_PERMISSIONS:
        permission_id = permission_ids[permission]
        existing = bind.execute(
            sa.text(
                "SELECT 1 FROM role_permissions "
                "WHERE role_id = :role_id AND permission_id = :permission_id"
            ),
            {"role_id": role_id, "permission_id": permission_id},
        ).scalar_one_or_none()
        if existing is not None:
            continue
        bind.execute(
            role_permissions.insert().values(
                role_id=role_id,
                permission_id=permission_id,
            )
        )
        bind.execute(
            tracked_grants.insert().values(
                role_id=role_id,
                permission_id=permission_id,
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    tracked = bind.execute(
        sa.text(
            f"SELECT role_id, permission_id FROM {GRANT_TRACKING_TABLE}"
        )
    ).fetchall()
    for role_id, permission_id in tracked:
        bind.execute(
            sa.text(
                "DELETE FROM role_permissions "
                "WHERE role_id = :role_id AND permission_id = :permission_id"
            ),
            {"role_id": role_id, "permission_id": permission_id},
        )

    op.drop_table(GRANT_TRACKING_TABLE)
