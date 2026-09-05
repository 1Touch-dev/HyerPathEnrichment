"""ORM models for Brand: a presentation-only storefront concept
(Decision: docs/adr/0019-tenancy-model.md). Brand is NOT a data-isolation boundary — no
query anywhere filters by brand_id, and no code path uses Brand to decide who can see
what. It exists purely to drive custom-domain routing, per-brand chatbot config, and
landing-page tier presentation on top of the one shared candidate/recruiter pool."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, JsonDoc


class Brand(Base):
    """A branded storefront: name, slug, optional custom domain, chatbot config,
    landing-page tier config. Never an FK target for any access-control decision —
    see docs/adr/0019-tenancy-model.md's Decision §1."""

    __tablename__ = "brands"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    # Custom domain for this brand's storefront, e.g. "careers.acme.com". NULL means
    # this brand has no dedicated domain and is only reachable via the platform's
    # default host + /b/{slug} routing. Used only for CORS origin resolution
    # (machine-1-tenancy-core/04-cors-and-ratelimit-retrofit.md) and storefront
    # routing — never a query filter.
    custom_domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Per-brand prompt/tone/branding overrides for the CV-chat service. See
    # machine-2-parallel-tracks/11-per-brand-chatbot-config.md for the schema this
    # JSON blob follows; this chunk only reserves the column.
    chatbot_config: Mapped[dict[str, Any] | None] = mapped_column(JsonDoc, nullable=True)
    # Which landing-page tier/segment sub-pages this brand exposes (e.g. which of
    # post-tenancy-features/02-brand-landing-pages.md's /b/{slug}/{tier} pages are
    # enabled and their tier-specific copy/config). This chunk only reserves the
    # column; that chunk owns the actual shape.
    landing_page_tier_config: Mapped[dict[str, Any] | None] = mapped_column(JsonDoc, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class RecruiterCandidateAssignment(Base):
    """Ownership/responsibility marker only — many-to-many. Recording or omitting a
    row here has NO effect on which candidates a recruiter can search, view, or act
    on; every recruiter can already work every candidate in the shared pool. This
    table exists solely to back "my assigned candidates" views and reporting. See
    docs/adr/0019-tenancy-model.md's Decision §4 — do not add an authorization check
    anywhere that reads this table."""

    __tablename__ = "recruiter_candidate_assignments"

    __table_args__ = (
        UniqueConstraint(
            "recruiter_user_id", "candidate_user_id", name="uq_recruiter_candidate_assignment"
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    recruiter_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    candidate_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
