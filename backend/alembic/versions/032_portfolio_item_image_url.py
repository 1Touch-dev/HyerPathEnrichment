"""Add image_url to portfolio_items (thumbnail/image for a portfolio item).

Revision ID: 032_portfolio_item_image_url
Revises: 031_merge_jobcv_stab_heads
Create Date: 2026-08-14
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "032_portfolio_item_image_url"
down_revision: str | Sequence[str] | None = "031_merge_jobcv_stab_heads"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "portfolio_items",
        sa.Column("image_url", sa.String(2048), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("portfolio_items", "image_url")
