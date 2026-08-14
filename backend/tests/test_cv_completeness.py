"""Tests for app.domain.cv_completeness — pure functions, no DB, no mocks needed."""

from __future__ import annotations

from app.domain.candidate import CVData
from app.domain.cv_completeness import (
    FIELD_WEIGHTS,
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
    cv = CVData(email="a@b.com")  # only the `email` field present
    score = completeness_score(cv)
    # `email` is not a richness-scaled list field, so its full weight applies.
    assert score == round(FIELD_WEIGHTS["email"], 4)


def test_completeness_score_full_cv_is_one():
    cv = CVData(
        email="a@b.com",
        phone="555-1234",
        linkedin_url="https://linkedin.com/in/a",
        technical_skills=["python", "sql", "go"],
        total_years_experience=5.0,
        desired_roles=["engineer", "developer", "architect"],
        desired_locations=["remote", "nyc", "sf"],
        remote_preference="remote",
    )
    assert completeness_score(cv) == 1.0


def test_completeness_score_empty_cv_is_zero():
    assert completeness_score(CVData()) == 0.0


def test_completeness_score_richer_list_scores_higher_though_both_not_missing():
    """A 1-item list is 'not missing' per compute_missing_fields, but should
    still score lower than a 3+-item list thanks to the richness factor."""
    sparse_cv = CVData(
        email="a@b.com",
        phone="555-1234",
        linkedin_url="https://linkedin.com/in/a",
        technical_skills=["python"],
        total_years_experience=5.0,
        desired_roles=["engineer"],
        desired_locations=["remote"],
        remote_preference="remote",
    )
    rich_cv = CVData(
        email="a@b.com",
        phone="555-1234",
        linkedin_url="https://linkedin.com/in/a",
        technical_skills=["python", "sql", "go"],
        total_years_experience=5.0,
        desired_roles=["engineer"],
        desired_locations=["remote"],
        remote_preference="remote",
    )
    assert "technical_skills" not in compute_missing_fields(sparse_cv)
    assert "technical_skills" not in compute_missing_fields(rich_cv)
    assert completeness_score(sparse_cv) < completeness_score(rich_cv)


def test_compute_missing_fields_unchanged_regression():
    """Regression guard: compute_missing_fields() must stay a binary
    presence/absence check, unaffected by FIELD_WEIGHTS/richness scoring,
    since cv_chat_service.py's question flow depends on this exact output."""
    assert compute_missing_fields(CVData()) == [
        "email",
        "phone",
        "linkedin_url",
        "technical_skills",
        "total_years_experience",
        "desired_roles",
        "desired_locations",
        "remote_preference",
    ]
    full_cv = CVData(
        email="a@b.com",
        phone="555-1234",
        linkedin_url="https://linkedin.com/in/a",
        technical_skills=["python"],
        total_years_experience=5.0,
        desired_roles=["engineer"],
        desired_locations=["remote"],
        remote_preference="remote",
    )
    assert compute_missing_fields(full_cv) == []
    partial_cv = CVData(email="a@b.com", technical_skills=["python"])
    missing = compute_missing_fields(partial_cv)
    assert "email" not in missing
    assert "technical_skills" not in missing
    assert "phone" in missing
    assert "remote_preference" in missing


def test_question_for_field_known_field():
    assert "email" in question_for_field("email").lower()


def test_question_for_field_unknown_field_falls_back_gracefully():
    q = question_for_field("some_new_field")
    assert "some new field" in q.lower()
