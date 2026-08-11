"""Add portfolio_profiles table for candidate portfolio pages.

Revision ID: 027_portfolio_profiles
Revises: 026_cv_feedback_reports
Create Date: 2026-08-08
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "027_portfolio_profiles"
down_revision: Union[str, Sequence[str], None] = "026_cv_feedback_reports"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    uuid_type = postgresql.UUID(as_uuid=True) if dialect == "postgresql" else sa.String(36)

    op.create_table(
        "portfolio_profiles",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("user_id", uuid_type, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("slug", sa.String(64), nullable=False),  # DNS-safe charset, per Decision 4
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("headline", sa.String(255), nullable=True),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_portfolio_profiles_user_id", "portfolio_profiles", ["user_id"], unique=True)
    op.create_index("ix_portfolio_profiles_slug", "portfolio_profiles", ["slug"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_portfolio_profiles_slug", table_name="portfolio_profiles")
    op.drop_index("ix_portfolio_profiles_user_id", table_name="portfolio_profiles")
    op.drop_table("portfolio_profiles")
