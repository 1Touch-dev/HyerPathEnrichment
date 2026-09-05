"""Prometheus metrics for Module 1 (AI Job Matching & Notifications)."""

from __future__ import annotations

from typing import Self

try:
    from prometheus_client import Counter, Histogram
except ImportError:  # pragma: no cover - optional dependency

    class _NoopMetric:
        def labels(self, *_args: object, **_kwargs: object) -> Self:
            return self

        def inc(self, *_args: object, **_kwargs: object) -> None:
            return None

        def observe(self, *_args: object, **_kwargs: object) -> None:
            return None

        def time(self) -> Self:
            return self

        def __enter__(self) -> Self:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

    def Counter(*_args: object, **_kwargs: object) -> _NoopMetric:  # type: ignore[no-redef]
        return _NoopMetric()

    def Histogram(*_args: object, **_kwargs: object) -> _NoopMetric:  # type: ignore[no-redef]
        return _NoopMetric()


job_matching_scans_total = Counter(
    "job_matching_scans_total", "Total job-matching scans run", ["status"]
)

job_matching_postings_scraped_total = Counter(
    "job_matching_postings_scraped_total", "Total job postings scraped", ["source"]
)

job_matching_explanations_generated_total = Counter(
    "job_matching_explanations_generated_total", "Total LLM explanations generated"
)

job_matching_digest_emails_sent_total = Counter(
    "job_matching_digest_emails_sent_total", "Total digest emails sent"
)

job_matching_webhook_notifications_total = Counter(
    "job_matching_webhook_notifications_total",
    "Total job-match webhook delivery attempts",
    ["status"],
)

job_matching_push_notifications_total = Counter(
    "job_matching_push_notifications_total",
    "Total job-match push notification delivery attempts",
    ["status"],
)

job_matching_scan_duration_seconds = Histogram(
    "job_matching_scan_duration_seconds", "Duration of a single candidate scan"
)

job_matching_similarity_fallback_fired_total = Counter(
    "job_matching_similarity_fallback_fired_total",
    "Total times the similarity-threshold relaxation fallback fired (strict pass returned "
    "fewer than min_results)",
)

job_matching_apply_clicks_total = Counter(
    "job_matching_apply_clicks_total", "Total Apply-button clicks recorded"
)
