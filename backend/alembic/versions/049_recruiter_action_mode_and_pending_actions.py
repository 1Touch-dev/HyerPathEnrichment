"""Add users.recruiter_action_mode; create pending_recruiter_actions and
role_suggestions tables (Machine 2, Track 09).

Revision ID: 049_recruiter_action_mode_and_pending_actions
Revises: 048_outreach_strategy_dimension
Create Date: 2026-08-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "049_recruiter_action_mode_and_pending_actions"
down_revision: str | Sequence[str] | None = "048_outreach_strategy_dimension"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Leadership-confirmed (2026-08-24/25 Q&A, see machine-2-parallel-tracks/09's
# "Ambiguities resolved" section): default must stay approval_required, not
# autonomous — this is a release-blocking review boundary for this track.
_RECRUITER_ACTION_MODE_DEFAULT = "approval_required"


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    uuid_type = postgresql.UUID(as_uuid=True) if dialect == "postgresql" else sa.String(36)

    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(
            sa.Column(
                "recruiter_action_mode",
                sa.String(20),
                nullable=False,
                server_default=_RECRUITER_ACTION_MODE_DEFAULT,
            )
        )

    op.create_table(
        "pending_recruiter_actions",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column(
            "candidate_user_id",
            uuid_type,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "recruiter_user_id",
            uuid_type,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("action_type", sa.String(20), nullable=False),
        sa.Column(
            "job_match_id",
            uuid_type,
            sa.ForeignKey("job_matches.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending", index=True),
        sa.Column("recruiter_note", sa.Text(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "role_suggestions",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column(
            "candidate_user_id",
            uuid_type,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "recruiter_user_id",
            uuid_type,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "job_match_id",
            uuid_type,
            sa.ForeignKey("job_matches.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("recruiter_note", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending", index=True),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("role_suggestions")
    op.drop_table("pending_recruiter_actions")

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("recruiter_action_mode")
