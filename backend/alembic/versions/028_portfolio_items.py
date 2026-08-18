"""Add portfolio_items table for projects/links on a candidate's portfolio page.

Revision ID: 028_portfolio_items
Revises: 027_portfolio_profiles
Create Date: 2026-08-08
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "028_portfolio_items"
down_revision: Union[str, Sequence[str], None] = "027_portfolio_profiles"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    uuid_type = postgresql.UUID(as_uuid=True) if dialect == "postgresql" else sa.String(36)

    op.create_table(
        "portfolio_items",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("profile_id", uuid_type, sa.ForeignKey("portfolio_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("item_type", sa.String(20), nullable=False),  # "github"|"live_demo"|"case_study"|"other"
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_portfolio_items_profile_id", "portfolio_items", ["profile_id"])


def downgrade() -> None:
    op.drop_index("ix_portfolio_items_profile_id", table_name="portfolio_items")
    op.drop_table("portfolio_items")
