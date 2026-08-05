from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, JsonDoc
from app.domain.enums import JobStatus


class JobRecord(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: f"job_{uuid4().hex}"
    )
    user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(32), default=JobStatus.queued.value, nullable=False)
    request_payload: Mapped[dict[str, Any]] = mapped_column(JsonDoc, default=dict, nullable=False)
    dossier_payload: Mapped[dict[str, Any]] = mapped_column(JsonDoc, default=dict, nullable=False)
    identifier_hashes: Mapped[list[str]] = mapped_column(JsonDoc, default=list, nullable=False)
    progress_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        JsonDoc, default=None, nullable=True
    )
    parent_job_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    child_job_ids: Mapped[list[str]] = mapped_column(JsonDoc, default=list, nullable=False)
    tier_assignment: Mapped[list[str] | None] = mapped_column(JsonDoc, nullable=True)
    is_internal: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
