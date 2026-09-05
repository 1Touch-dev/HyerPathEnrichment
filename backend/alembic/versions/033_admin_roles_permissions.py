"""Add roles, permissions, and role_permissions tables (Admin Module RBAC).

Revision ID: 033_admin_roles_permissions
Revises: 032_portfolio_item_image_url
Create Date: 2026-08-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "033_admin_roles_permissions"
down_revision: str | Sequence[str] | None = "032_portfolio_item_image_url"
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
        "roles",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("name", sa.String(64), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "permissions",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("resource", sa.String(64), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.UniqueConstraint("resource", "action", name="uq_permissions_resource_action"),
    )

    op.create_table(
        "role_permissions",
        sa.Column(
            "role_id", uuid_type, sa.ForeignKey("roles.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "permission_id",
            uuid_type,
            sa.ForeignKey("permissions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("role_id", "permission_id", name="pk_role_permissions"),
    )

    op.create_index("ix_roles_name", "roles", ["name"])
    op.create_index("ix_permissions_resource", "permissions", ["resource"])


def downgrade() -> None:
    op.drop_index("ix_permissions_resource", table_name="permissions")
    op.drop_index("ix_roles_name", table_name="roles")
    op.drop_table("role_permissions")
    op.drop_table("permissions")
    op.drop_table("roles")
