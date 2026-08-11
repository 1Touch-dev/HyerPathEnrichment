"""Add job_swipe_actions table — candidate swipe reactions on Module 1's job_matches.

Revision ID: 029_job_swipe_actions
Revises: 028_portfolio_items
Create Date: 2026-08-08
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "029_job_swipe_actions"
down_revision: Union[str, Sequence[str], None] = "028_portfolio_items"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    uuid_type = postgresql.UUID(as_uuid=True) if dialect == "postgresql" else sa.String(36)

    op.create_table(
        "job_swipe_actions",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("job_match_id", uuid_type, sa.ForeignKey("job_matches.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("user_id", uuid_type, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),  # "right"(interested)|"left"(pass)|"up"(super_like)
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_job_swipe_actions_user_id", "job_swipe_actions", ["user_id"])
    op.create_index("ix_job_swipe_actions_job_match_id", "job_swipe_actions", ["job_match_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_job_swipe_actions_job_match_id", table_name="job_swipe_actions")
    op.drop_index("ix_job_swipe_actions_user_id", table_name="job_swipe_actions")
    op.drop_table("job_swipe_actions")
