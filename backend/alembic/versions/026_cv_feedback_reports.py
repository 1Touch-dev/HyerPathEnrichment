"""Add cv_feedback_reports table for AI-generated CV improvement suggestions.

Revision ID: 026_cv_feedback_reports
Revises: 025_cv_chat_sessions
Create Date: 2026-08-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "026_cv_feedback_reports"
down_revision: str | Sequence[str] | None = "025_cv_chat_sessions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    uuid_type = postgresql.UUID(as_uuid=True) if dialect == "postgresql" else sa.String(36)
    jsonb_type = postgresql.JSONB() if dialect == "postgresql" else sa.JSON()

    op.create_table(
        "cv_feedback_reports",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column(
            "document_id",
            uuid_type,
            sa.ForeignKey("candidate_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id", uuid_type, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "target_role", sa.String(255), nullable=True
        ),  # optional role the candidate is optimizing for
        sa.Column("ats_score", sa.Integer(), nullable=False),  # 0-100
        sa.Column("strengths", jsonb_type, nullable=False, server_default="[]"),
        sa.Column("improvements", jsonb_type, nullable=False, server_default="[]"),
        sa.Column(
            "rewritten_bullets", jsonb_type, nullable=False, server_default="[]"
        ),  # [{original, rewritten, rationale}]
        sa.Column(
            "accepted_bullet_indices", jsonb_type, nullable=False, server_default="[]"
        ),  # candidate's explicit accepts
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_cv_feedback_reports_document_id", "cv_feedback_reports", ["document_id"])
    op.create_index("ix_cv_feedback_reports_user_id", "cv_feedback_reports", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_cv_feedback_reports_user_id", table_name="cv_feedback_reports")
    op.drop_index("ix_cv_feedback_reports_document_id", table_name="cv_feedback_reports")
    op.drop_table("cv_feedback_reports")
