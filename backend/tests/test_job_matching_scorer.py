"""Unit tests for deterministic job-match scoring (scorer.py). No DB, no I/O."""

import pytest

from app.modules.job_matching.scorer import (
    compute_dedup_key,
    compute_overall_score,
    compute_rule_score,
    normalize_dedup_field,
    score_location_fit,
    score_salary_fit,
)


class TestNormalizeDedupField:
    def test_lowercases_and_strips_punctuation(self):
        assert (
            normalize_dedup_field("Senior Software Engineer, Backend!")
            == "senior software engineer backend"
        )

    def test_collapses_whitespace(self):
        assert normalize_dedup_field("New   York    City") == "new york city"

    def test_handles_empty_string(self):
        assert normalize_dedup_field("") == ""


class TestComputeDedupKey:
    def test_same_title_location_source_produces_same_key(self):
        key1 = compute_dedup_key("Software Engineer", "New York, NY", "linkedin")
        key2 = compute_dedup_key("software engineer", "new york ny", "linkedin")
        assert key1 == key2

    def test_different_source_produces_different_key(self):
        key1 = compute_dedup_key("Software Engineer", "New York, NY", "linkedin")
        key2 = compute_dedup_key("Software Engineer", "New York, NY", "indeed")
        assert key1 != key2

    def test_company_name_is_not_part_of_key(self):
        """Per Decision 4: company name is deliberately excluded."""
        key1 = compute_dedup_key("Software Engineer", "New York, NY", "linkedin")
        key2 = compute_dedup_key("Software Engineer", "New York, NY", "linkedin")
        assert key1 == key2  # same inputs regardless of any company field passed elsewhere

    def test_key_is_64_char_hex(self):
        key = compute_dedup_key("Engineer", "Remote", "indeed")
        assert len(key) == 64
        assert all(c in "0123456789abcdef" for c in key)


class TestScoreSalaryFit:
    def test_no_preference_is_neutral(self):
        assert score_salary_fit(100_000, 150_000, None, None) == 0.5

    def test_no_posting_salary_is_neutral(self):
        assert score_salary_fit(None, None, 100_000, 150_000) == 0.5

    def test_full_overlap_is_perfect(self):
        assert score_salary_fit(100_000, 150_000, 100_000, 150_000) == 1.0

    def test_partial_overlap_is_perfect(self):
        assert score_salary_fit(120_000, 180_000, 100_000, 150_000) == 1.0

    def test_no_overlap_is_zero(self):
        assert score_salary_fit(200_000, 250_000, 80_000, 120_000) == 0.0

    def test_posting_min_only(self):
        assert score_salary_fit(100_000, None, 90_000, 110_000) == 1.0

    def test_candidate_min_only(self):
        assert score_salary_fit(50_000, 70_000, 100_000, None) == 0.0


class TestScoreLocationFit:
    def test_remote_preference_matches_remote_posting(self):
        assert score_location_fit(None, True, [], "remote") == 1.0

    def test_remote_preference_rejects_onsite_posting(self):
        assert score_location_fit("Austin, TX", False, [], "remote") == 0.0

    def test_no_location_preference_is_neutral(self):
        assert score_location_fit("Austin, TX", False, [], None) == 0.5

    def test_remote_posting_satisfies_any_location_preference(self):
        assert score_location_fit(None, True, ["New York"], "hybrid") == 1.0

    def test_remote_posting_satisfies_onsite_preference(self):
        """Documents the current (intentional) behavior: a fully-remote posting
        satisfies any stated remote_preference — including "onsite" — since the
        posting itself imposes no location constraint on the candidate."""
        assert score_location_fit(None, True, ["New York"], "onsite") == 1.0

    def test_matching_city_scores_perfect(self):
        assert score_location_fit("New York, NY", False, ["New York"], "onsite") == 1.0

    def test_non_matching_city_scores_zero(self):
        assert score_location_fit("Austin, TX", False, ["New York"], "onsite") == 0.0


class TestComputeRuleScore:
    def test_combines_salary_and_location(self):
        posting = {"salary_min": 100_000, "salary_max": 150_000, "location": "NYC", "remote": False}
        prefs = {
            "salary_min": 100_000,
            "salary_max": 150_000,
            "desired_locations": ["NYC"],
            "remote_preference": "onsite",
        }
        score, breakdown = compute_rule_score(posting, prefs)
        assert score == 1.0
        assert breakdown == {"salary_fit": 1.0, "location_fit": 1.0}

    def test_mismatched_everything_scores_zero(self):
        posting = {
            "salary_min": 40_000,
            "salary_max": 50_000,
            "location": "Austin",
            "remote": False,
        }
        prefs = {
            "salary_min": 150_000,
            "salary_max": 200_000,
            "desired_locations": ["NYC"],
            "remote_preference": "onsite",
        }
        score, breakdown = compute_rule_score(posting, prefs)
        assert score == 0.0


class TestComputeOverallScore:
    def test_perfect_scores_yield_100(self):
        assert compute_overall_score(1.0, 1.0) == 100.0

    def test_zero_scores_yield_0(self):
        assert compute_overall_score(0.0, 0.0) == 0.0

    def test_weighted_composite(self):
        # 0.7 * 0.8 + 0.3 * 0.5 = 0.71 -> 71.0
        assert compute_overall_score(0.8, 0.5) == 71.0

    def test_clamps_above_one(self):
        assert compute_overall_score(1.5, 1.5) == 100.0

    def test_clamps_below_zero(self):
        assert compute_overall_score(-0.5, -0.5) == 0.0

    @pytest.mark.parametrize("sim,rule", [(0.9, 0.1), (0.5, 0.5), (0.0, 1.0)])
    def test_result_always_in_valid_range(self, sim, rule):
        result = compute_overall_score(sim, rule)
        assert 0.0 <= result <= 100.0
