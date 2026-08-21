"""Prometheus metrics for Module 4, Module E (JD-aware interview practice)."""

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


jd_practice_questions_generated_total = Counter(
    "jd_practice_questions_generated_total",
    "Total JD-tailored interview questions generated via POST /api/jd-practice/questions",
)

jd_practice_daily_limit_hit_total = Counter(
    "jd_practice_daily_limit_hit_total",
    "Total times the JD-tailored practice daily generation limit rejected a request",
)
