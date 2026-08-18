"""Add webhook_url to candidate_job_preferences (webhook notification target).

Revision ID: 022_webhook_url_preferences
Revises: 021_job_matches
Create Date: 2026-08-10
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "022_webhook_url_preferences"
down_revision: Union[str, Sequence[str], None] = "021_job_matches"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "candidate_job_preferences",
        sa.Column("webhook_url", sa.String(2048), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("candidate_job_preferences", "webhook_url")
