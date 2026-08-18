"""Add impersonation_sessions table (Admin Module — support impersonation).

Revision ID: 037_admin_impersonation_sessions
Revises: 036_admin_feature_flags
Create Date: 2026-08-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "037_admin_impersonation_sessions"
down_revision: str | Sequence[str] | None = "036_admin_feature_flags"
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
        "impersonation_sessions",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column(
            "admin_user_id", uuid_type, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "target_user_id", uuid_type, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("token_jti", sa.String(64), nullable=False, unique=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_impersonation_sessions_admin_user_id", "impersonation_sessions", ["admin_user_id"])
    op.create_index("ix_impersonation_sessions_target_user_id", "impersonation_sessions", ["target_user_id"])


def downgrade() -> None:
    op.drop_index("ix_impersonation_sessions_target_user_id", table_name="impersonation_sessions")
    op.drop_index("ix_impersonation_sessions_admin_user_id", table_name="impersonation_sessions")
    op.drop_table("impersonation_sessions")
