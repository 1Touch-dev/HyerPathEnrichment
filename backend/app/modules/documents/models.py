"""ORM models for document processing jobs and candidate documents."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, JsonDoc

try:
    from pgvector.sqlalchemy import Vector

    PGVECTOR_AVAILABLE = True
except ImportError:
    PGVECTOR_AVAILABLE = False


class CandidateDocument(Base):
    """Candidate document (CV, cover letter) with processing metadata."""

    __tablename__ = "candidate_documents"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_type: Mapped[str] = mapped_column(String(20), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(512), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_data: Mapped[dict[str, Any] | None] = mapped_column(JsonDoc, nullable=True)
    processing_status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DocumentJob(Base):
    """Document processing job tracking."""

    __tablename__ = "document_jobs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("candidate_documents.id", ondelete="CASCADE"), nullable=True
    )
    job_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)
    progress: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    result: Mapped[dict[str, Any] | None] = mapped_column(JsonDoc, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class DocumentEmbedding(Base):
    """Document chunk embedding with vector similarity support.

    Stores text chunks with their embeddings for semantic search.
    Uses pgvector on PostgreSQL, JSON array on SQLite.
    """

    __tablename__ = "document_embeddings"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("candidate_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    # Special handling for embedding column - pgvector on PostgreSQL, Text on SQLite
    if PGVECTOR_AVAILABLE:
        # PostgreSQL with pgvector extension
        embedding = mapped_column(Vector(1536), nullable=False)
    else:
        # SQLite fallback - store as JSON text array
        _embedding_json: Mapped[str] = mapped_column("embedding", Text, nullable=False)

        @property  # type: ignore[no-redef]
        def embedding(self) -> list[float]:
            """Get embedding as list of floats."""
            if isinstance(self._embedding_json, list):
                return self._embedding_json
            result: list[float] = json.loads(self._embedding_json)
            return result

        @embedding.setter
        def embedding(self, value: list[float]) -> None:
            """Set embedding from list of floats."""
            if isinstance(value, str):
                self._embedding_json = value
            else:
                self._embedding_json = json.dumps(value)


class CvChatSession(Base):
    """CV-completeness chatbot conversation state (Decision 1/2)."""

    __tablename__ = "cv_chat_sessions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("candidate_documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    missing_fields_at_start: Mapped[list[str]] = mapped_column(
        JsonDoc, default=list, nullable=False
    )
    fields_resolved: Mapped[list[str]] = mapped_column(JsonDoc, default=list, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CvChatMessage(Base):
    """Single turn in a CV-completeness chat session."""

    __tablename__ = "cv_chat_messages"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("cv_chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(10), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    field_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    tool_call_result: Mapped[dict[str, Any] | None] = mapped_column(JsonDoc, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class CvFeedbackReport(Base):
    """AI-generated CV improvement suggestions (Decision 3)."""

    __tablename__ = "cv_feedback_reports"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("candidate_documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_role: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ats_score: Mapped[int] = mapped_column(Integer, nullable=False)
    strengths: Mapped[list[str]] = mapped_column(JsonDoc, default=list, nullable=False)
    improvements: Mapped[list[str]] = mapped_column(JsonDoc, default=list, nullable=False)
    rewritten_bullets: Mapped[list[dict[str, Any]]] = mapped_column(
        JsonDoc, default=list, nullable=False
    )
    accepted_bullet_indices: Mapped[list[int]] = mapped_column(
        JsonDoc, default=list, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
