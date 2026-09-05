"""Add feature_flags table (Admin Module — DB-backed kill switches).

Revision ID: 036_admin_feature_flags
Revises: 035_admin_audit_logs
Create Date: 2026-08-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "036_admin_feature_flags"
down_revision: str | Sequence[str] | None = "035_admin_audit_logs"
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
        "feature_flags",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("key", sa.String(128), nullable=False, unique=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("value", _json_type(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "updated_by",
            uuid_type,
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_feature_flags_key", "feature_flags", ["key"])


def downgrade() -> None:
    op.drop_index("ix_feature_flags_key", table_name="feature_flags")
    op.drop_table("feature_flags")
