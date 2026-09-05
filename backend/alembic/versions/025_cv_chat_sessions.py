"""Add cv_chat_sessions and cv_chat_messages tables for CV-completeness chatbot.

Revision ID: 025_cv_chat_sessions
Revises: 024_push_subscriptions
Create Date: 2026-08-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "025_cv_chat_sessions"
down_revision: str | Sequence[str] | None = "024_push_subscriptions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    uuid_type = postgresql.UUID(as_uuid=True) if dialect == "postgresql" else sa.String(36)
    jsonb_type = postgresql.JSONB() if dialect == "postgresql" else sa.JSON()

    op.create_table(
        "cv_chat_sessions",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column(
            "user_id", uuid_type, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "document_id",
            uuid_type,
            sa.ForeignKey("candidate_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "status", sa.String(20), nullable=False, server_default="active"
        ),  # "active"|"completed"|"abandoned"
        sa.Column("missing_fields_at_start", jsonb_type, nullable=False, server_default="[]"),
        sa.Column("fields_resolved", jsonb_type, nullable=False, server_default="[]"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_cv_chat_sessions_user_id", "cv_chat_sessions", ["user_id"])
    op.create_index("ix_cv_chat_sessions_document_id", "cv_chat_sessions", ["document_id"])

    op.create_table(
        "cv_chat_messages",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column(
            "session_id",
            uuid_type,
            sa.ForeignKey("cv_chat_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(10), nullable=False),  # "assistant"|"user"
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "field_name", sa.String(50), nullable=True
        ),  # which CVData field this message targets, if any
        sa.Column(
            "tool_call_result", jsonb_type, nullable=True
        ),  # validated value recorded via record_cv_answer tool
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_cv_chat_messages_session_id", "cv_chat_messages", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_cv_chat_messages_session_id", table_name="cv_chat_messages")
    op.drop_table("cv_chat_messages")
    op.drop_index("ix_cv_chat_sessions_document_id", table_name="cv_chat_sessions")
    op.drop_index("ix_cv_chat_sessions_user_id", table_name="cv_chat_sessions")
    op.drop_table("cv_chat_sessions")
