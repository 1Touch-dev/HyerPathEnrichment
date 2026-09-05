"""Prometheus metrics for Module 4, Module D (interview scheduling)."""

from __future__ import annotations

from typing import Self

try:
    from prometheus_client import Counter
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


interview_schedules_created_total = Counter(
    "interview_schedules_created_total",
    "Total interview schedules created/updated via POST /api/interviews/matches/{match_id}/schedule",
)

interview_reminders_sent_total = Counter(
    "interview_reminders_sent_total",
    "Total interview reminder notifications (email+push) sent",
)
