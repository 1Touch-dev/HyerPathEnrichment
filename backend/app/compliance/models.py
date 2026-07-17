from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, JsonDoc
from app.domain.enums import DsarStatus


class SuppressionRecord(Base):
    __tablename__ = "suppression_list"

    identifier_hash: Mapped[str] = mapped_column(String(128), primary_key=True)
    reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    identifier_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    job_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    details: Mapped[dict[str, Any]] = mapped_column(JsonDoc, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class DsarRecord(Base):
    __tablename__ = "dsar_requests"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    identifier_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    request_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default=DsarStatus.pending.value, nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JsonDoc, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
