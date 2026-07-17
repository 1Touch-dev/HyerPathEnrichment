from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class PhotoCacheRecord(Base):
    __tablename__ = "photo_cache"

    slug_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    slug: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    asset_key: Mapped[str] = mapped_column(String(512), default="", nullable=False)
    asset_url: Mapped[str] = mapped_column(String(1024), default="", nullable=False)
    extraction_method: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
