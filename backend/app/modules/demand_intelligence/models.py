"""ORM models for country-level job-demand aggregates."""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class CountryDemandSnapshot(Base):
    """One day's aggregate posting count for a (country, normalized_role) pair.

    Populated by a periodic worker job (see service.py), not computed on-demand per
    request — recomputing a full country x role aggregate on every API call would be
    an expensive full-table scan of job_postings on every dashboard load.
    """

    __tablename__ = "country_demand_snapshots"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    country_iso2: Mapped[str] = mapped_column(String(2), nullable=False, index=True)
    # Lowercased, whitespace-trimmed role title bucket, e.g. "software engineer" —
    # not a foreign key to any existing "role" table (none exists); free-text bucket
    # matching how JobPosting.title itself is free text.
    role_bucket: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    posting_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    remote_posting_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_salary_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    avg_salary_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
