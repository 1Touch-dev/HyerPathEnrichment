"""Tests for app.domain.cv_completeness — pure functions, no DB, no mocks needed."""

from __future__ import annotations

from app.domain.candidate import CVData
from app.domain.cv_completeness import (
    FIELD_WEIGHTS,
    completeness_score,
    compute_missing_fields,
    question_for_field,
)

_ALL_REQUIRED_FIELDS = [
    "email",
    "phone",
    "linkedin_url",
    "github_url",
    "portfolio_url",
    "technical_skills",
    "total_years_experience",
    "highest_degree",
    "desired_roles",
    "desired_locations",
    "remote_preference",
]

_FULL_CV_KWARGS = {
    "email": "a@b.com",
    "phone": "555-1234",
    "linkedin_url": "https://linkedin.com/in/a",
    "github_url": "https://github.com/a",
    "portfolio_url": "https://a.dev",
    "technical_skills": ["python"],
    "total_years_experience": 5.0,
    "highest_degree": "BS Computer Science",
    "desired_roles": ["engineer"],
    "desired_locations": ["remote"],
    "remote_preference": "remote",
}


def test_compute_missing_fields_all_missing_on_empty_cv():
    missing = compute_missing_fields(CVData())
    assert missing == _ALL_REQUIRED_FIELDS


def test_compute_missing_fields_none_missing_on_full_cv():
    cv = CVData(**_FULL_CV_KWARGS)
    assert compute_missing_fields(cv) == []


def test_compute_missing_fields_partial():
    cv = CVData(email="a@b.com", technical_skills=["python"])
    missing = compute_missing_fields(cv)
    assert "email" not in missing
    assert "technical_skills" not in missing
    assert "phone" in missing
    assert "remote_preference" in missing


def test_compute_missing_fields_github_and_portfolio_are_checked():
    """Feature-2 spec explicitly names GitHub and portfolio as fields the
    completeness scan must check for — regression guard that they're wired in."""
    cv = CVData(email="a@b.com")
    missing = compute_missing_fields(cv)
    assert "github_url" in missing
    assert "portfolio_url" in missing

    cv_with_links = CVData(
        email="a@b.com",
        github_url="https://github.com/a",
        portfolio_url="https://a.dev",
    )
    missing_with_links = compute_missing_fields(cv_with_links)
    assert "github_url" not in missing_with_links
    assert "portfolio_url" not in missing_with_links


def test_compute_missing_fields_education_is_checked():
    """Feature-2 spec explicitly names education as a field to check for —
    `highest_degree` is the CVData field that represents it."""
    cv = CVData(email="a@b.com")
    assert "highest_degree" in compute_missing_fields(cv)

    cv_with_degree = CVData(email="a@b.com", highest_degree="BS Computer Science")
    assert "highest_degree" not in compute_missing_fields(cv_with_degree)


def test_compute_missing_fields_zero_years_experience_is_not_missing():
    """0.0 years of experience is a real (if unusual) value, not an absent one —
    only `None` triggers "missing" for non-list/str fields."""
    cv = CVData(**{**_FULL_CV_KWARGS, "total_years_experience": 0.0})
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
        github_url="https://github.com/a",
        portfolio_url="https://a.dev",
        technical_skills=["python", "sql", "go"],
        total_years_experience=5.0,
        highest_degree="BS Computer Science",
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
    sparse_cv = CVData(**_FULL_CV_KWARGS)
    rich_cv = CVData(**{**_FULL_CV_KWARGS, "technical_skills": ["python", "sql", "go"]})
    assert "technical_skills" not in compute_missing_fields(sparse_cv)
    assert "technical_skills" not in compute_missing_fields(rich_cv)
    assert completeness_score(sparse_cv) < completeness_score(rich_cv)


def test_compute_missing_fields_unchanged_regression():
    """Regression guard: compute_missing_fields() must stay a binary
    presence/absence check, unaffected by FIELD_WEIGHTS/richness scoring,
    since cv_chat_service.py's question flow depends on this exact output."""
    assert compute_missing_fields(CVData()) == _ALL_REQUIRED_FIELDS
    full_cv = CVData(**_FULL_CV_KWARGS)
    assert compute_missing_fields(full_cv) == []
    partial_cv = CVData(email="a@b.com", technical_skills=["python"])
    missing = compute_missing_fields(partial_cv)
    assert "email" not in missing
    assert "technical_skills" not in missing
    assert "phone" in missing
    assert "remote_preference" in missing


def test_question_for_field_known_field():
    assert "email" in question_for_field("email").lower()


def test_question_for_field_github_and_portfolio_have_dedicated_questions():
    assert "github" in question_for_field("github_url").lower()
    assert "portfolio" in question_for_field("portfolio_url").lower()


def test_question_for_field_unknown_field_falls_back_gracefully():
    q = question_for_field("some_new_field")
    assert "some new field" in q.lower()
