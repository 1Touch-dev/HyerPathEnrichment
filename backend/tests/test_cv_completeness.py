"""Tests for app.domain.cv_completeness — pure functions, no DB, no mocks needed."""

from __future__ import annotations

import pytest

from app.domain.candidate import CVData
from app.domain.cv_completeness import (
    FIELD_WEIGHTS,
    PROGRESSIVE_FIELDS,
    REQUIRED_FIELDS,
    completeness_score,
    compute_missing_fields,
    compute_missing_progressive_fields,
    question_for_field,
    question_for_progressive_field,
    should_generate_prep_strategy_suggestion,
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


def test_field_weights_sum_to_one():
    """The module docstring claims FIELD_WEIGHTS forms a weighted distribution
    that sums to 1.0 — lock that invariant in so a future edit that adds/removes
    a field or rebalances weights without preserving the total is caught here,
    rather than silently skewing completeness_score()'s 0.0-1.0 range."""
    assert sum(FIELD_WEIGHTS.values()) == pytest.approx(1.0)


def test_field_weights_cover_exactly_required_fields():
    """Guards against a future field being added to REQUIRED_FIELDS without a
    matching FIELD_WEIGHTS entry (today that would silently KeyError inside
    completeness_score() at runtime with no test catching it beforehand), and
    vice versa (a stale weight left behind for a removed field)."""
    assert set(FIELD_WEIGHTS.keys()) == set(REQUIRED_FIELDS)


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


def test_completeness_score_unaffected_by_progressive_fields():
    """Regression guard (spec-mandated): a CVData with all REQUIRED_FIELDS set scores
    identically to before progressive profiling shipped, whether or not the new
    progressive fields happen to be set — adding interests/learning_style/
    prep_timeline_weeks must not silently change completeness_score() or
    compute_missing_fields()."""
    cv_without_progressive = CVData(**_FULL_CV_KWARGS)
    cv_with_progressive = CVData(
        **_FULL_CV_KWARGS,
        interests=["hiking"],
        learning_style="visual",
        prep_timeline_weeks=4,
    )
    assert completeness_score(cv_without_progressive) == completeness_score(cv_with_progressive)
    assert compute_missing_fields(cv_without_progressive) == compute_missing_fields(
        cv_with_progressive
    )
    assert "interests" not in REQUIRED_FIELDS
    assert "learning_style" not in REQUIRED_FIELDS
    assert "prep_timeline_weeks" not in REQUIRED_FIELDS
    assert "interests" not in FIELD_WEIGHTS
    assert "learning_style" not in FIELD_WEIGHTS
    assert "prep_timeline_weeks" not in FIELD_WEIGHTS


def test_compute_missing_progressive_fields_all_missing_on_empty_cv():
    missing = compute_missing_progressive_fields(CVData())
    assert missing == PROGRESSIVE_FIELDS
    assert missing == ["interests", "learning_style", "prep_timeline_weeks"]


def test_compute_missing_progressive_fields_none_missing_when_all_set():
    cv = CVData(
        interests=["hiking", "chess"],
        learning_style="visual",
        prep_timeline_weeks=4,
    )
    assert compute_missing_progressive_fields(cv) == []


def test_compute_missing_progressive_fields_partial():
    cv = CVData(learning_style="hands_on")
    missing = compute_missing_progressive_fields(cv)
    assert "learning_style" not in missing
    assert "interests" in missing
    assert "prep_timeline_weeks" in missing


def test_question_for_progressive_field_known_field():
    assert "interested" in question_for_progressive_field("interests").lower()
    assert "learn best" in question_for_progressive_field("learning_style").lower()
    assert "weeks" in question_for_progressive_field("prep_timeline_weeks").lower()


def test_question_for_progressive_field_unknown_field_falls_back_gracefully():
    q = question_for_progressive_field("some_new_field")
    assert "some new field" in q.lower()


def test_should_generate_prep_strategy_suggestion_false_when_learning_style_unset():
    cv = CVData(prep_timeline_weeks=4)
    assert should_generate_prep_strategy_suggestion(cv) is False


def test_should_generate_prep_strategy_suggestion_false_when_timeline_unset():
    cv = CVData(learning_style="visual")
    assert should_generate_prep_strategy_suggestion(cv) is False


def test_should_generate_prep_strategy_suggestion_true_when_both_set_and_no_suggestion_yet():
    cv = CVData(learning_style="visual", prep_timeline_weeks=4)
    assert should_generate_prep_strategy_suggestion(cv) is True


def test_should_generate_prep_strategy_suggestion_false_once_suggestion_already_set():
    """No double-generation: once prep_strategy_suggestion is populated, the trigger
    must not fire again even though both prep-relevant fields remain set."""
    cv = CVData(
        learning_style="visual",
        prep_timeline_weeks=4,
        prep_strategy_suggestion="Already generated.",
    )
    assert should_generate_prep_strategy_suggestion(cv) is False


def test_should_generate_prep_strategy_suggestion_order_independent():
    """Order doesn't matter — either field can be answered first in the chat."""
    cv_learning_style_first = CVData(learning_style="reading")
    cv_learning_style_first.prep_timeline_weeks = 2
    assert should_generate_prep_strategy_suggestion(cv_learning_style_first) is True

    cv_timeline_first = CVData(prep_timeline_weeks=2)
    cv_timeline_first.learning_style = "reading"
    assert should_generate_prep_strategy_suggestion(cv_timeline_first) is True
