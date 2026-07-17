from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, JsonDoc
from app.domain.enums import JobStatus


class JobRecord(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: f"job_{uuid4().hex}")
    status: Mapped[str] = mapped_column(String(32), default=JobStatus.queued.value, nullable=False)
    request_payload: Mapped[dict[str, Any]] = mapped_column(JsonDoc, default=dict, nullable=False)
    dossier_payload: Mapped[dict[str, Any]] = mapped_column(JsonDoc, default=dict, nullable=False)
    identifier_hashes: Mapped[list[str]] = mapped_column(JsonDoc, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
