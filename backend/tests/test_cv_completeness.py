"""Tests for app.domain.cv_completeness — pure functions, no DB, no mocks needed."""

from __future__ import annotations

from app.domain.candidate import CVData
from app.domain.cv_completeness import (
    completeness_score,
    compute_missing_fields,
    question_for_field,
)


def test_compute_missing_fields_all_missing_on_empty_cv():
    missing = compute_missing_fields(CVData())
    assert missing == [
        "email",
        "phone",
        "linkedin_url",
        "technical_skills",
        "total_years_experience",
        "desired_roles",
        "desired_locations",
        "remote_preference",
    ]


def test_compute_missing_fields_none_missing_on_full_cv():
    cv = CVData(
        email="a@b.com",
        phone="555-1234",
        linkedin_url="https://linkedin.com/in/a",
        technical_skills=["python"],
        total_years_experience=5.0,
        desired_roles=["engineer"],
        desired_locations=["remote"],
        remote_preference="remote",
    )
    assert compute_missing_fields(cv) == []


def test_compute_missing_fields_partial():
    cv = CVData(email="a@b.com", technical_skills=["python"])
    missing = compute_missing_fields(cv)
    assert "email" not in missing
    assert "technical_skills" not in missing
    assert "phone" in missing
    assert "remote_preference" in missing


def test_compute_missing_fields_zero_years_experience_is_not_missing():
    """0.0 years of experience is a real (if unusual) value, not an absent one —
    only `None` triggers "missing" for non-list/str fields."""
    cv = CVData(
        email="a@b.com",
        phone="555-1234",
        linkedin_url="https://linkedin.com/in/a",
        technical_skills=["python"],
        total_years_experience=0.0,
        desired_roles=["engineer"],
        desired_locations=["remote"],
        remote_preference="remote",
    )
    assert "total_years_experience" not in compute_missing_fields(cv)


def test_completeness_score_matches_present_fraction():
    cv = CVData(email="a@b.com")  # 1 of 8 fields present, 7 missing
    score = completeness_score(cv)
    assert score == round(1 / 8, 4)


def test_completeness_score_full_cv_is_one():
    cv = CVData(
        email="a@b.com",
        phone="555-1234",
        linkedin_url="https://linkedin.com/in/a",
        technical_skills=["python"],
        total_years_experience=5.0,
        desired_roles=["engineer"],
        desired_locations=["remote"],
        remote_preference="remote",
    )
    assert completeness_score(cv) == 1.0


def test_completeness_score_empty_cv_is_zero():
    assert completeness_score(CVData()) == 0.0


def test_question_for_field_known_field():
    assert "email" in question_for_field("email").lower()


def test_question_for_field_unknown_field_falls_back_gracefully():
    q = question_for_field("some_new_field")
    assert "some new field" in q.lower()
