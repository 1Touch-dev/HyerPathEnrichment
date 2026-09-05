"""Add candidate_documents table for CV and document storage.

Stores uploaded candidate documents (CVs, cover letters) with metadata,
processing status, and deduplication via file hash.

Revision ID: 008_candidate_documents
Revises: 009_enable_pgvector
Create Date: 2026-08-04
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "008_candidate_documents"
down_revision: str | Sequence[str] | None = "007_add_user_id_to_dsar"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add candidate_documents table with security and deduplication features."""
    bind = op.get_bind()
    dialect = bind.dialect.name

    # Use UUID type for Postgres, String for SQLite
    uuid_type = postgresql.UUID() if dialect == "postgresql" else sa.String(36)

    op.create_table(
        "candidate_documents",
        sa.Column("id", uuid_type, primary_key=True, nullable=False),
        sa.Column("user_id", uuid_type, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("document_type", sa.String(20), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("storage_path", sa.String(512), nullable=False),
        sa.Column("file_hash", sa.String(64), nullable=False),
        sa.Column("file_size_bytes", sa.Integer, nullable=False),
        sa.Column("raw_text", sa.Text, nullable=True),
        sa.Column(
            "extracted_data",
            postgresql.JSONB() if dialect == "postgresql" else sa.JSON(),
            nullable=True,
        ),
        sa.Column("processing_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column(
            "created_at", sa.DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")
        ),
        sa.Column(
            "updated_at", sa.DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")
        ),
    )

    # Create indexes for common queries
    op.create_index("idx_candidate_documents_user_id", "candidate_documents", ["user_id"])
    op.create_index("idx_candidate_documents_file_hash", "candidate_documents", ["file_hash"])
    op.create_index("idx_candidate_documents_status", "candidate_documents", ["processing_status"])


def downgrade() -> None:
    """Remove candidate_documents table and indexes."""
    op.drop_index("idx_candidate_documents_status", table_name="candidate_documents")
    op.drop_index("idx_candidate_documents_file_hash", table_name="candidate_documents")
    op.drop_index("idx_candidate_documents_user_id", table_name="candidate_documents")
    op.drop_table("candidate_documents")
