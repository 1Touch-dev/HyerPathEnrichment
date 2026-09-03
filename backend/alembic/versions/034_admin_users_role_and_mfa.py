"""Add role_id + MFA schema columns to users (Admin Module).

Revision ID: 034_admin_users_role_and_mfa
Revises: 033_admin_roles_permissions
Create Date: 2026-08-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "034_admin_users_role_and_mfa"
down_revision: str | Sequence[str] | None = "033_admin_roles_permissions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _uuid_type():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return postgresql.UUID(as_uuid=True)
    return sa.String(36)


def upgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"
    role_id_type = _uuid_type()

    # SQLite has no native ALTER TABLE ADD CONSTRAINT/ADD FOREIGN KEY support —
    # batch mode (recreate-table) is required there, matching the existing
    # pattern in 006_add_user_authentication.py for the same "add FK column to
    # an existing table" shape. Postgres supports these ALTERs directly.
    if is_sqlite:
        with op.batch_alter_table("users", schema=None) as batch_op:
            batch_op.add_column(sa.Column("role_id", role_id_type, nullable=True))
            batch_op.add_column(sa.Column("mfa_secret", sa.String(64), nullable=True))
            batch_op.add_column(
                sa.Column("mfa_enabled", sa.Boolean(), nullable=False, server_default=sa.false())
            )
            batch_op.add_column(
                sa.Column("mfa_enrolled_at", sa.DateTime(timezone=True), nullable=True)
            )
            batch_op.create_foreign_key(
                "fk_users_role_id", "roles", ["role_id"], ["id"], ondelete="SET NULL"
            )
            batch_op.create_index("ix_users_role_id", ["role_id"])
    else:
        op.add_column("users", sa.Column("role_id", role_id_type, nullable=True))
        op.add_column("users", sa.Column("mfa_secret", sa.String(64), nullable=True))
        op.add_column(
            "users",
            sa.Column("mfa_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
        op.add_column(
            "users", sa.Column("mfa_enrolled_at", sa.DateTime(timezone=True), nullable=True)
        )
        op.create_foreign_key(
            "fk_users_role_id", "users", "roles", ["role_id"], ["id"], ondelete="SET NULL"
        )
        op.create_index("ix_users_role_id", "users", ["role_id"])


def downgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    if is_sqlite:
        with op.batch_alter_table("users", schema=None) as batch_op:
            batch_op.drop_index("ix_users_role_id")
            batch_op.drop_constraint("fk_users_role_id", type_="foreignkey")
            batch_op.drop_column("mfa_enrolled_at")
            batch_op.drop_column("mfa_enabled")
            batch_op.drop_column("mfa_secret")
            batch_op.drop_column("role_id")
    else:
        op.drop_index("ix_users_role_id", table_name="users")
        op.drop_constraint("fk_users_role_id", "users", type_="foreignkey")
        op.drop_column("users", "mfa_enrolled_at")
        op.drop_column("users", "mfa_enabled")
        op.drop_column("users", "mfa_secret")
        op.drop_column("users", "role_id")
