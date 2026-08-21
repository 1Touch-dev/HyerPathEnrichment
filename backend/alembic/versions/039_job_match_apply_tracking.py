"""Add apply_clicked_at and applied_at to job_matches (Module 4, Module B).

Revision ID: 039_job_match_apply_tracking
Revises: 038_practice_audio_recordings_voice_tone
Create Date: 2026-08-20
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "039_job_match_apply_tracking"
down_revision: str | Sequence[str] | None = "038_practice_audio_recordings_voice_tone"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("job_matches") as batch_op:
        batch_op.add_column(
            sa.Column("apply_clicked_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("job_matches") as batch_op:
        batch_op.drop_column("applied_at")
        batch_op.drop_column("apply_clicked_at")
