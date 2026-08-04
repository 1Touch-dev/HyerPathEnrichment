"""Add document_jobs table for tracking document processing jobs.

Tracks job status, progress, and results for document processing workflow.

Revision ID: 011_document_jobs
Revises: 008_candidate_documents
Create Date: 2026-08-04
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "011_document_jobs"
down_revision: Union[str, Sequence[str], None] = "008_candidate_documents"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add document_jobs table for job tracking."""
    bind = op.get_bind()
    dialect = bind.dialect.name

    # Use UUID type for Postgres, String for SQLite
    uuid_type = postgresql.UUID() if dialect == "postgresql" else sa.String(36)

    op.create_table(
        "document_jobs",
        sa.Column("id", uuid_type, primary_key=True, nullable=False),
        sa.Column("user_id", uuid_type, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_id", uuid_type, sa.ForeignKey("candidate_documents.id", ondelete="CASCADE"), nullable=True),
        sa.Column("job_type", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("progress", sa.Float, nullable=False, server_default="0.0"),
        sa.Column(
            "result",
            postgresql.JSONB() if dialect == "postgresql" else sa.JSON(),
            nullable=True,
        ),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    # Create indexes for common queries
    op.create_index("idx_document_jobs_user_id", "document_jobs", ["user_id"])
    op.create_index("idx_document_jobs_status", "document_jobs", ["status"])


def downgrade() -> None:
    """Remove document_jobs table and indexes."""
    op.drop_index("idx_document_jobs_status", table_name="document_jobs")
    op.drop_index("idx_document_jobs_user_id", table_name="document_jobs")
    op.drop_table("document_jobs")
