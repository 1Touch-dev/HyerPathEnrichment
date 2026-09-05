"""Add message_type + custom_instruction to outreach_messages (Module 4, Module G).

Revision ID: 041_outreach_message_type
Revises: 040_job_match_application_status
Create Date: 2026-08-20
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "041_outreach_message_type"
down_revision: str | Sequence[str] | None = "040_job_match_application_status"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("outreach_messages") as batch_op:
        batch_op.add_column(
            sa.Column("message_type", sa.String(20), nullable=False, server_default="email")
        )
        batch_op.add_column(sa.Column("custom_instruction", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("outreach_messages") as batch_op:
        batch_op.drop_column("custom_instruction")
        batch_op.drop_column("message_type")
