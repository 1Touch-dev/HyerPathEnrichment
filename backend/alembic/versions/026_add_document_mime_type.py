"""Add mime_type column to candidate_documents

Revision ID: 026_add_document_mime_type
Revises: 025_merge_job_match_heads
Create Date: 2026-08-17
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "026_add_document_mime_type"
down_revision: str | Sequence[str] | None = "025_merge_job_match_heads"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add a nullable mime_type column so reprocessing can pick the right
    extractor (PDF vs DOCX) without re-guessing from the filename.

    Nullable so existing rows (uploaded before this migration) don't break;
    they simply can't be reprocessed until re-uploaded.
    """
    op.add_column(
        "candidate_documents",
        sa.Column("mime_type", sa.String(length=128), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("candidate_documents", "mime_type")
