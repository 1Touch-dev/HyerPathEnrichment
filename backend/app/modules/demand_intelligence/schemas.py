"""HTTP request/response schemas for the demand-intelligence module."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

CountryTier = Literal["tier_1", "tier_2", "tier_3"]


class CountryDemandRow(BaseModel):
    country_iso2: str
    role_bucket: str
    posting_count: int
    remote_posting_count: int
    avg_salary_min: int | None
    avg_salary_max: int | None
    snapshot_date: date
    tier: CountryTier


class TopCountriesResponse(BaseModel):
    role: str
    results: list[CountryDemandRow]
    generated_at: datetime
