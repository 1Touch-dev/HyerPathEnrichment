"""Tests for `_build_jd_generation_messages` (Module 4, Module E, §9.7).

Parallel to test_question_bank.py's `TestQuestionGeneration`/
`TestPersonalizedGeneration` coverage of `_build_generation_messages`'s
personalization branch, but for the JD-tailored sibling builder.
"""

from __future__ import annotations

from app.services.question_generator import (
    _MAX_JD_CHARS,
    CandidateContext,
    JobContext,
    _build_jd_generation_messages,
)


def _make_job_context(description: str) -> JobContext:
    return JobContext(job_description=description, job_title="Backend Engineer", company="Acme")


class TestBuildJdGenerationMessages:
    def test_includes_jd_excerpt_verbatim_when_under_limit(self):
        description = "We need someone to own our payments retry logic and on-call rotation."
        job_context = _make_job_context(description)

        messages = _build_jd_generation_messages(
            category="technical",
            difficulty="medium",
            job_context=job_context,
            candidate_context=None,
        )

        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        content = messages[1]["content"]
        assert description in content
        assert job_context.job_title in content
        assert job_context.company in content

    def test_truncates_jd_excerpt_at_max_jd_chars(self):
        long_description = "A" * (_MAX_JD_CHARS + 500)
        job_context = _make_job_context(long_description)

        messages = _build_jd_generation_messages(
            category="technical",
            difficulty="medium",
            job_context=job_context,
            candidate_context=None,
        )
        content = messages[1]["content"]

        assert long_description[:_MAX_JD_CHARS] in content
        # The excerpt must be truncated -- the full over-limit string (with
        # its trailing, never-included tail) must not appear verbatim.
        assert long_description not in content

    def test_includes_candidate_context_details_when_provided(self):
        job_context = _make_job_context("Own our checkout service.")
        candidate_context = CandidateContext(
            skills=["Python", "Kubernetes"],
            target_role="Backend Engineer",
            years_experience=5,
            recent_job_titles=["Senior Software Engineer"],
        )

        messages = _build_jd_generation_messages(
            category="technical",
            difficulty="medium",
            job_context=job_context,
            candidate_context=candidate_context,
        )
        content = messages[1]["content"]

        assert "Python" in content
        assert "Kubernetes" in content
        assert "Backend Engineer" in content
        assert "5" in content
        assert "Senior Software Engineer" in content

    def test_omits_candidate_context_details_when_not_provided(self):
        job_context = _make_job_context("Own our checkout service.")

        messages = _build_jd_generation_messages(
            category="technical",
            difficulty="medium",
            job_context=job_context,
            candidate_context=None,
        )
        content = messages[1]["content"]

        assert "Tailor this question to a candidate with these skills" not in content

    def test_pluralizes_question_count_and_requests_json_array_when_count_gt_1(self):
        job_context = _make_job_context("Own our checkout service.")

        messages = _build_jd_generation_messages(
            category="behavioral",
            difficulty="easy",
            job_context=job_context,
            candidate_context=None,
            count=3,
        )
        content = messages[1]["content"]

        assert "3 unique interview questions" in content
        assert "Return a JSON array with 3 question objects." in content
