"""Add job_posting_embeddings table for pgvector-based job matching.

Revision ID: 019_job_posting_embeddings
Revises: 018_job_postings
Create Date: 2026-08-08
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision: str = "019_job_posting_embeddings"
down_revision: Union[str, Sequence[str], None] = "018_job_postings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
        op.execute(
            text("""
            CREATE TABLE job_posting_embeddings (
                id UUID PRIMARY KEY,
                job_posting_id UUID NOT NULL REFERENCES job_postings(id) ON DELETE CASCADE,
                embedding vector(1536) NOT NULL,
                token_count INTEGER NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """)
        )
        op.execute(
            "CREATE INDEX idx_job_posting_embeddings_hnsw ON job_posting_embeddings "
            "USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)"
        )
        op.create_index(
            "ix_job_posting_embeddings_posting_id",
            "job_posting_embeddings",
            ["job_posting_id"],
            unique=True,
        )
    else:
        op.create_table(
            "job_posting_embeddings",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column(
                "job_posting_id",
                sa.String(36),
                sa.ForeignKey("job_postings.id", ondelete="CASCADE"),
                nullable=False,
                unique=True,
            ),
            sa.Column(
                "embedding", sa.Text(), nullable=False
            ),  # JSON-encoded list[float], SQLite fallback
            sa.Column("token_count", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )


def downgrade() -> None:
    op.drop_table("job_posting_embeddings")
