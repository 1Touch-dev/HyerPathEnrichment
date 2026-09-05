"""Create interview_questions table

Revision ID: 016_interview_questions
Revises: 014_document_embeddings
Create Date: 2026-08-07 15:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import text

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "016_interview_questions"
down_revision: str | None = "014_document_embeddings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create interview_questions table with job role and technology indexing."""
    connection = op.get_bind()
    dialect_name = connection.dialect.name

    if dialect_name == "postgresql":
        # PostgreSQL: use native array types and JSONB
        op.execute(
            text("""
            CREATE TABLE interview_questions (
                id UUID NOT NULL,
                question_text TEXT NOT NULL,
                question_category VARCHAR(50) NOT NULL,
                difficulty VARCHAR(20) NOT NULL,
                job_roles TEXT[] NOT NULL,
                technologies TEXT[] NOT NULL,
                sample_answer TEXT,
                scoring_rubric JSONB,
                source VARCHAR(100),
                usage_count INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL,
                PRIMARY KEY (id)
            )
        """)
        )

        # Create standard indexes
        op.create_index("idx_questions_category", "interview_questions", ["question_category"])
        op.create_index("idx_questions_difficulty", "interview_questions", ["difficulty"])

        # Create GIN index on job_roles array for fast array containment queries
        op.execute(
            "CREATE INDEX idx_questions_job_roles ON interview_questions USING gin (job_roles)"
        )

        # Create GIN index on technologies array
        op.execute(
            "CREATE INDEX idx_questions_technologies ON interview_questions "
            "USING gin (technologies)"
        )

    else:
        # SQLite fallback: store arrays and JSONB as TEXT
        op.create_table(
            "interview_questions",
            sa.Column("id", sa.String(36), nullable=False),
            sa.Column("question_text", sa.Text(), nullable=False),
            sa.Column("question_category", sa.String(50), nullable=False),
            sa.Column("difficulty", sa.String(20), nullable=False),
            sa.Column("job_roles", sa.Text(), nullable=False),  # JSON array as text
            sa.Column("technologies", sa.Text(), nullable=False),  # JSON array as text
            sa.Column("sample_answer", sa.Text(), nullable=True),
            sa.Column("scoring_rubric", sa.Text(), nullable=True),  # JSONB as text
            sa.Column("source", sa.String(100), nullable=True),
            sa.Column("usage_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )

        # Create standard indexes
        op.create_index("idx_questions_category", "interview_questions", ["question_category"])
        op.create_index("idx_questions_difficulty", "interview_questions", ["difficulty"])


def downgrade() -> None:
    """Drop interview_questions table and indexes."""
    connection = op.get_bind()
    dialect_name = connection.dialect.name

    if dialect_name == "postgresql":
        # Drop GIN indexes first
        op.drop_index("idx_questions_technologies", table_name="interview_questions")
        op.drop_index("idx_questions_job_roles", table_name="interview_questions")
        op.drop_index("idx_questions_difficulty", table_name="interview_questions")
        op.drop_index("idx_questions_category", table_name="interview_questions")

        # Drop table
        op.drop_table("interview_questions")

    else:
        # SQLite
        op.drop_index("idx_questions_difficulty", table_name="interview_questions")
        op.drop_index("idx_questions_category", table_name="interview_questions")
        op.drop_table("interview_questions")
