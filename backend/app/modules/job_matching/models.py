"""ORM models for job matching: postings, embeddings, preferences, matches."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, JsonDoc

try:
    from pgvector.sqlalchemy import Vector

    PGVECTOR_AVAILABLE = True
except ImportError:
    PGVECTOR_AVAILABLE = False


class JobPosting(Base):
    """Deduplicated job posting scraped from job boards."""

    __tablename__ = "job_postings"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    dedup_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True, unique=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    company: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    remote: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    description_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    salary_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    sources_seen: Mapped[list[str]] = mapped_column(JsonDoc, default=list, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)


class JobPostingEmbedding(Base):
    """Embedding vector for a job posting (parallel to DocumentEmbedding)."""

    __tablename__ = "job_posting_embeddings"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    job_posting_id: Mapped[UUID] = mapped_column(
        ForeignKey("job_postings.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    if PGVECTOR_AVAILABLE:
        embedding = mapped_column(Vector(1536), nullable=False)
    else:
        import json as _json

        _embedding_json: Mapped[str] = mapped_column("embedding", Text, nullable=False)

        @property  # type: ignore[no-redef]
        def embedding(self) -> list[float]:
            if isinstance(self._embedding_json, list):
                return self._embedding_json
            return list(self._json.loads(self._embedding_json))

        @embedding.setter
        def embedding(self, value: list[float]) -> None:
            self._embedding_json = value if isinstance(value, str) else self._json.dumps(value)


class CandidateJobPreferences(Base):
    """Per-candidate job-matching targeting criteria and notification settings."""

    __tablename__ = "candidate_job_preferences"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    source_document_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("candidate_documents.id", ondelete="SET NULL"), nullable=True
    )
    desired_roles: Mapped[list[str]] = mapped_column(JsonDoc, default=list, nullable=False)
    desired_locations: Mapped[list[str]] = mapped_column(JsonDoc, default=list, nullable=False)
    remote_preference: Mapped[str | None] = mapped_column(String(20), nullable=True)
    salary_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_currency: Mapped[str] = mapped_column(String(10), default="USD", nullable=False)
    notification_channels: Mapped[list[str]] = mapped_column(
        JsonDoc, default=lambda: ["email"], nullable=False
    )
    digest_frequency: Mapped[str] = mapped_column(String(20), default="daily", nullable=False)
    is_scan_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    last_scanned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class JobMatch(Base):
    """Scored candidate-to-job-posting pairing."""

    __tablename__ = "job_matches"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_posting_id: Mapped[UUID] = mapped_column(
        ForeignKey("job_postings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    similarity_score: Mapped[float] = mapped_column(Float, nullable=False)
    rule_score: Mapped[float] = mapped_column(Float, nullable=False)
    overall_score: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    score_breakdown: Mapped[dict[str, Any]] = mapped_column(JsonDoc, default=dict, nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    explanation_generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    viewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    feedback: Mapped[str | None] = mapped_column(String(10), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
