"""Add Phase 2 moderation columns (Admin Module — review queue support).

Revision ID: 040_phase2_moderation_columns
Revises: 039_admin_review_queue
Create Date: 2026-08-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "040_phase2_moderation_columns"
down_revision: str | Sequence[str] | None = "039_admin_review_queue"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _uuid_type():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return postgresql.UUID(as_uuid=True)
    return sa.String(36)


def upgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"
    uuid_type = _uuid_type()

    # SQLite has no native ALTER TABLE ADD CONSTRAINT/ADD FOREIGN KEY support —
    # batch mode (recreate-table) is required there for the moderated_by FK,
    # matching the existing pattern in 034_admin_users_role_and_mfa.py for the
    # same "add FK column to an existing table" shape. Postgres supports these
    # ALTERs directly.
    if is_sqlite:
        with op.batch_alter_table("job_postings", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "moderation_status", sa.String(16), nullable=False, server_default="active"
                )
            )
            batch_op.add_column(sa.Column("moderated_by", uuid_type, nullable=True))
            batch_op.add_column(sa.Column("moderated_at", sa.DateTime(timezone=True), nullable=True))
            batch_op.create_foreign_key(
                "fk_job_postings_moderated_by", "users", ["moderated_by"], ["id"], ondelete="SET NULL"
            )
    else:
        op.add_column(
            "job_postings",
            sa.Column("moderation_status", sa.String(16), nullable=False, server_default="active"),
        )
        op.add_column("job_postings", sa.Column("moderated_by", uuid_type, nullable=True))
        op.add_column(
            "job_postings", sa.Column("moderated_at", sa.DateTime(timezone=True), nullable=True)
        )
        op.create_foreign_key(
            "fk_job_postings_moderated_by",
            "job_postings",
            "users",
            ["moderated_by"],
            ["id"],
            ondelete="SET NULL",
        )

    op.add_column(
        "candidate_documents", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "portfolio_profiles",
        sa.Column("admin_hidden", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "outreach_messages",
        sa.Column("admin_blocked", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    op.drop_column("outreach_messages", "admin_blocked")
    op.drop_column("portfolio_profiles", "admin_hidden")
    op.drop_column("candidate_documents", "deleted_at")

    if is_sqlite:
        with op.batch_alter_table("job_postings", schema=None) as batch_op:
            batch_op.drop_constraint("fk_job_postings_moderated_by", type_="foreignkey")
            batch_op.drop_column("moderated_at")
            batch_op.drop_column("moderated_by")
            batch_op.drop_column("moderation_status")
    else:
        op.drop_constraint("fk_job_postings_moderated_by", "job_postings", type_="foreignkey")
        op.drop_column("job_postings", "moderated_at")
        op.drop_column("job_postings", "moderated_by")
        op.drop_column("job_postings", "moderation_status")
