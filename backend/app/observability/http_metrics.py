"""HTTP golden-signal metrics scraped by Prometheus from GET /metrics."""

from __future__ import annotations

from typing import Self

try:
    from prometheus_client import Counter, Gauge, Histogram
except ImportError:  # pragma: no cover - optional dependency

    class _NoopMetric:
        def labels(self, *_args: object, **_kwargs: object) -> Self:
            return self

        def inc(self, *_args: object, **_kwargs: object) -> None:
            return None

        def observe(self, *_args: object, **_kwargs: object) -> None:
            return None

        def set(self, *_args: object, **_kwargs: object) -> None:
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

    def Gauge(*_args: object, **_kwargs: object) -> _NoopMetric:  # type: ignore[no-redef]
        return _NoopMetric()


http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests handled by the API",
    ["method", "status"],
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)

rq_queue_length = Gauge(
    "rq_queue_length",
    "Current Redis Queue depth observed at scrape time",
)


def observe_http_request(method: str, status_code: int, duration_seconds: float) -> None:
    normalized_method = (method or "GET").upper()
    http_requests_total.labels(method=normalized_method, status=str(status_code)).inc()
    http_request_duration_seconds.labels(method=normalized_method).observe(duration_seconds)


def refresh_queue_depth_metric() -> None:
    """Best-effort RQ depth refresh so Prometheus scrapes a current gauge."""
    try:
        from app.observability.health_alerts import queue_depth_snapshot

        snapshot = queue_depth_snapshot()
    except Exception:
        return
    if snapshot is None:
        return
    rq_queue_length.set(snapshot["queued"])
