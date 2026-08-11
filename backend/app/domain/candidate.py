"""Candidate domain models for CV/resume structured data."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CVData(BaseModel):
    """Structured data extracted from candidate CV/resume.

    Contains contact info, skills, experience, education, industries,
    certifications, and job preferences.
    Includes completeness scoring to track missing fields.
    """

    # Contact
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    linkedin_url: str | None = None
    github_url: str | None = None
    portfolio_url: str | None = None

    # Skills
    technical_skills: list[str] = Field(default_factory=list)
    soft_skills: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)

    # Experience
    total_years_experience: float | None = None
    current_role: str | None = None
    current_company: str | None = None
    work_history: list[dict[str, Any]] | None = None
    industries: list[str] = Field(default_factory=list)

    # Education
    highest_degree: str | None = None
    field_of_study: str | None = None
    certifications: list[str] = Field(default_factory=list)

    # Preferences
    desired_roles: list[str] = Field(default_factory=list)
    desired_locations: list[str] = Field(default_factory=list)
    remote_preference: str | None = None  # "remote"/"hybrid"/"onsite"
    salary_expectation: dict[str, Any] | None = None

    # Metadata
    completeness_score: float = 0.0  # 0.0 to 1.0
    missing_fields: list[str] = Field(default_factory=list)
