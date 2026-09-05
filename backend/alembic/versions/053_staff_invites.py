"""Create staff_invites table (machine-1-tenancy-core/05-org-invite-flow.md).

Revision ID: 053_staff_invites
Revises: 052_create_brands_and_candidate_assignments
Create Date: 2026-08-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "053_staff_invites"
down_revision: str | Sequence[str] | None = "052_create_brands_and_candidate_assignments"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _uuid_type():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return postgresql.UUID(as_uuid=True)
    return sa.String(36)


def upgrade() -> None:
    uuid_type = _uuid_type()

    op.create_table(
        "staff_invites",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("token", sa.String(64), nullable=False),
        sa.Column("role_name", sa.String(64), nullable=False, server_default="recruiter"),
        sa.Column(
            "invited_by",
            uuid_type,
            sa.ForeignKey(
                "users.id", ondelete="SET NULL", name="fk_staff_invites_invited_by_users"
            ),
            nullable=True,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_staff_invites_email", "staff_invites", ["email"])
    op.create_index("ix_staff_invites_token", "staff_invites", ["token"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_staff_invites_token", table_name="staff_invites")
    op.drop_index("ix_staff_invites_email", table_name="staff_invites")
    op.drop_table("staff_invites")
