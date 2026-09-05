"""Add admin_review_queue table (Admin Module — moderation review queue).

Revision ID: 039_admin_review_queue
Revises: 038_admin_seed_roles_permissions
Create Date: 2026-08-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "039_admin_review_queue"
down_revision: str | Sequence[str] | None = "038_admin_seed_roles_permissions"
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
        "admin_review_queue",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("resource_type", sa.String(32), nullable=False),
        sa.Column("resource_id", uuid_type, nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("flag_reason", sa.Text(), nullable=True),
        sa.Column("flag_source", sa.String(16), nullable=False),
        sa.Column("flagged_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "reviewed_by",
            uuid_type,
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
    )

    op.create_index(
        "ix_admin_review_queue_status_flagged_at",
        "admin_review_queue",
        ["status", "flagged_at"],
    )
    op.create_index(
        "ix_admin_review_queue_resource",
        "admin_review_queue",
        ["resource_type", "resource_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_admin_review_queue_resource", table_name="admin_review_queue")
    op.drop_index("ix_admin_review_queue_status_flagged_at", table_name="admin_review_queue")
    op.drop_table("admin_review_queue")
