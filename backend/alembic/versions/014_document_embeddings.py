"""Create document_embeddings table with pgvector support

Revision ID: 012_document_embeddings
Revises: 011_document_jobs
Create Date: 2026-08-04 13:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import text

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "014_document_embeddings"
down_revision: str | None = "013_document_jobs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create document_embeddings table with pgvector extension."""
    # Enable pgvector extension (no-op on SQLite)
    connection = op.get_bind()
    dialect_name = connection.dialect.name

    if dialect_name == "postgresql":
        # Enable vector extension
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

        # Create table with vector column using raw SQL for pgvector type
        op.execute(
            text("""
            CREATE TABLE document_embeddings (
                id UUID NOT NULL,
                document_id UUID NOT NULL,
                chunk_index INTEGER NOT NULL,
                chunk_text TEXT NOT NULL,
                embedding vector(1536) NOT NULL,
                token_count INTEGER NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL,
                PRIMARY KEY (id),
                FOREIGN KEY (document_id) REFERENCES candidate_documents(id) ON DELETE CASCADE
            )
        """)
        )

        # Create indexes
        op.create_index("idx_embeddings_document", "document_embeddings", ["document_id"])

        # Create HNSW index for vector similarity search
        # HNSW parameters: m=16 (connections per layer), ef_construction=64 (index build quality)
        op.execute(
            "CREATE INDEX idx_embeddings_hnsw ON document_embeddings "
            "USING hnsw (embedding vector_cosine_ops) "
            "WITH (m = 16, ef_construction = 64)"
        )
    else:
        # SQLite fallback: store vectors as TEXT (JSON array)
        op.create_table(
            "document_embeddings",
            sa.Column("id", sa.String(36), nullable=False),
            sa.Column("document_id", sa.String(36), nullable=False),
            sa.Column("chunk_index", sa.Integer(), nullable=False),
            sa.Column("chunk_text", sa.Text(), nullable=False),
            sa.Column("embedding", sa.Text(), nullable=False),  # JSON array as text
            sa.Column("token_count", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(
                ["document_id"], ["candidate_documents.id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("id"),
        )

        # Create document index (no vector index on SQLite)
        op.create_index("idx_embeddings_document", "document_embeddings", ["document_id"])


def downgrade() -> None:
    """Drop document_embeddings table and indexes."""
    connection = op.get_bind()
    dialect_name = connection.dialect.name

    if dialect_name == "postgresql":
        # Drop indexes first
        op.drop_index("idx_embeddings_hnsw", table_name="document_embeddings")
        op.drop_index("idx_embeddings_document", table_name="document_embeddings")

        # Drop table
        op.drop_table("document_embeddings")

        # Note: We don't drop the vector extension as other tables might use it
    else:
        # SQLite
        op.drop_index("idx_embeddings_document", table_name="document_embeddings")
        op.drop_table("document_embeddings")
