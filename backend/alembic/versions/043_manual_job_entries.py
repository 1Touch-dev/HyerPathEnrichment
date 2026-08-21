"""Create manual_job_entries table; widen job_matches.job_posting_id to nullable
and add manual_job_entry_id + a CHECK enforcing exactly one source (Module 4, Module F).

Revision ID: 043_manual_job_entries
Revises: 042_interview_schedules
Create Date: 2026-08-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "043_manual_job_entries"
down_revision: str | Sequence[str] | None = "042_interview_schedules"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    uuid_type = postgresql.UUID(as_uuid=True) if dialect == "postgresql" else sa.String(36)

    op.create_table(
        "manual_job_entries",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column(
            "user_id",
            uuid_type,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("company", sa.String(255), nullable=False),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("source_label", sa.String(255), nullable=True),
        sa.Column("source_url", sa.String(2048), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    with op.batch_alter_table("job_matches") as batch_op:
        batch_op.alter_column("job_posting_id", existing_type=uuid_type, nullable=True)
        batch_op.add_column(
            sa.Column(
                "manual_job_entry_id",
                uuid_type,
                sa.ForeignKey(
                    "manual_job_entries.id",
                    ondelete="CASCADE",
                    name="fk_job_matches_manual_job_entry_id",
                ),
                nullable=True,
            )
        )
        # SQLite has no native CHECK-constraint alteration via batch mode the same way
        # Postgres does, but op.create_check_constraint works under batch_alter_table
        # for both dialects here since this is an ADD, not a modification of column
        # nullability under a constraint — consistent with how 033 (renumbered 036)
        # already used batch mode for a mixed add-column + add-constraint operation.
        batch_op.create_check_constraint(
            "ck_job_matches_exactly_one_source",
            "(job_posting_id IS NOT NULL AND manual_job_entry_id IS NULL) OR "
            "(job_posting_id IS NULL AND manual_job_entry_id IS NOT NULL)",
        )


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    uuid_type = postgresql.UUID(as_uuid=True) if dialect == "postgresql" else sa.String(36)

    # NOTE: alter_column(..., nullable=False) below will fail (by design, per §10.3's
    # data-safety note) if any real manual-entry JobMatch rows exist — their
    # job_posting_id is legitimately NULL. Downgrading after real manual entries
    # exist requires deleting those rows first, a deliberate, manual, ops-reviewed
    # decision, not something this migration silently papers over.
    with op.batch_alter_table("job_matches") as batch_op:
        batch_op.drop_constraint("ck_job_matches_exactly_one_source")
        batch_op.drop_column("manual_job_entry_id")
        batch_op.alter_column("job_posting_id", existing_type=uuid_type, nullable=False)
    op.drop_table("manual_job_entries")
