"""Add candidate_job_preferences table.

Revision ID: 020_candidate_job_preferences
Revises: 019_job_posting_embeddings
Create Date: 2026-08-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "020_candidate_job_preferences"
down_revision: str | Sequence[str] | None = "019_job_posting_embeddings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    uuid_type = postgresql.UUID(as_uuid=True) if dialect == "postgresql" else sa.String(36)
    jsonb_type = postgresql.JSONB() if dialect == "postgresql" else sa.JSON()

    op.create_table(
        "candidate_job_preferences",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column(
            "user_id",
            uuid_type,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "source_document_id",
            uuid_type,
            sa.ForeignKey("candidate_documents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("desired_roles", jsonb_type, nullable=False, server_default="[]"),
        sa.Column("desired_locations", jsonb_type, nullable=False, server_default="[]"),
        sa.Column("remote_preference", sa.String(20), nullable=True),  # "remote"|"hybrid"|"onsite"
        sa.Column("salary_min", sa.Integer(), nullable=True),
        sa.Column("salary_max", sa.Integer(), nullable=True),
        sa.Column("salary_currency", sa.String(10), nullable=False, server_default="USD"),
        sa.Column("notification_channels", jsonb_type, nullable=False, server_default='["email"]'),
        sa.Column(
            "digest_frequency", sa.String(20), nullable=False, server_default="daily"
        ),  # "daily"|"weekly"|"off"
        sa.Column("is_scan_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_scanned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_candidate_job_preferences_user_id",
        "candidate_job_preferences",
        ["user_id"],
        unique=True,
    )
    op.create_index(
        "ix_candidate_job_preferences_scan_enabled",
        "candidate_job_preferences",
        ["is_scan_enabled"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_candidate_job_preferences_scan_enabled", table_name="candidate_job_preferences"
    )
    op.drop_index("ix_candidate_job_preferences_user_id", table_name="candidate_job_preferences")
    op.drop_table("candidate_job_preferences")
