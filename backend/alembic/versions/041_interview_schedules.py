"""Create interview_schedules table (Module 4, Module D).

Revision ID: 041_interview_schedules
Revises: 040_job_match_application_status
Create Date: 2026-08-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "041_interview_schedules"
down_revision: str | Sequence[str] | None = "040_job_match_application_status"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    uuid_type = postgresql.UUID(as_uuid=True) if dialect == "postgresql" else sa.String(36)

    op.create_table(
        "interview_schedules",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column(
            "job_match_id",
            uuid_type,
            sa.ForeignKey("job_matches.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
            index=True,
        ),
        sa.Column(
            "user_id",
            uuid_type,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("reminder_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_interview_schedules_user_scheduled_at",
        "interview_schedules",
        ["user_id", "scheduled_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_interview_schedules_user_scheduled_at", table_name="interview_schedules")
    op.drop_table("interview_schedules")
