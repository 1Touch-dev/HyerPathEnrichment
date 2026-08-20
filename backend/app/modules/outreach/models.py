"""ORM model for outreach drafts."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, JsonDoc


class OutreachMessage(Base):
    """A single AI-drafted (and possibly sent) outreach message."""

    __tablename__ = "outreach_messages"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_match_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("job_matches.id", ondelete="SET NULL"), nullable=True
    )
    recipient_role_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    company_context_used: Mapped[dict[str, Any]] = mapped_column(
        JsonDoc, default=dict, nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False, index=True)
    message_type: Mapped[str] = mapped_column(
        String(20), default="email", nullable=False, index=True
    )
    custom_instruction: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
