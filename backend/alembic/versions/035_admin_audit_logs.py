"""Add admin_audit_logs table (Admin Module — router/middleware-captured writes).

Revision ID: 035_admin_audit_logs
Revises: 034_admin_users_role_and_mfa
Create Date: 2026-08-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "035_admin_audit_logs"
down_revision: str | Sequence[str] | None = "034_admin_users_role_and_mfa"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _uuid_type():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return postgresql.UUID(as_uuid=True)
    return sa.String(36)


def _json_type():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return postgresql.JSONB()
    return sa.JSON()


def upgrade() -> None:
    uuid_type = _uuid_type()

    op.create_table(
        "admin_audit_logs",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column(
            "actor_user_id",
            uuid_type,
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("impersonated_by", uuid_type, nullable=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("target_type", sa.String(64), nullable=False),
        sa.Column("target_id", sa.String(64), nullable=True),
        sa.Column("before", _json_type(), nullable=True),
        sa.Column("after", _json_type(), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("captured_by", sa.String(16), nullable=False, server_default="explicit"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_index("ix_admin_audit_logs_actor_user_id", "admin_audit_logs", ["actor_user_id"])
    op.create_index("ix_admin_audit_logs_action", "admin_audit_logs", ["action"])
    op.create_index("ix_admin_audit_logs_target_type", "admin_audit_logs", ["target_type"])
    op.create_index("ix_admin_audit_logs_created_at", "admin_audit_logs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_admin_audit_logs_created_at", table_name="admin_audit_logs")
    op.drop_index("ix_admin_audit_logs_target_type", table_name="admin_audit_logs")
    op.drop_index("ix_admin_audit_logs_action", table_name="admin_audit_logs")
    op.drop_index("ix_admin_audit_logs_actor_user_id", table_name="admin_audit_logs")
    op.drop_table("admin_audit_logs")
