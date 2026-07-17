from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class SignalRecord(Base):
    __tablename__ = "signals"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: f"sig_{uuid4().hex}")
    source: Mapped[str] = mapped_column(String(32), default="changedetection", nullable=False)
    watch_id: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str] = mapped_column(String(512), default="", nullable=False)
    url: Mapped[str] = mapped_column(String(2048), default="", nullable=False)
    signal_timestamp: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
