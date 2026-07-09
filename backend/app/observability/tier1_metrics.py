"""Prometheus counters for Tier 1 LinkedIn photo enrichment."""

from __future__ import annotations

try:
    from prometheus_client import Counter
except ImportError:  # pragma: no cover - optional dependency

    class _NoopMetric:
        def labels(self, *_args: object, **_kwargs: object) -> _NoopMetric:
            return self

        def inc(self, *_args: object, **_kwargs: object) -> None:
            return None

    def Counter(*_args: object, **_kwargs: object) -> _NoopMetric:  # type: ignore[misc]
        return _NoopMetric()


tier1_cache_hits_total = Counter(
    "tier1_cache_hits_total",
    "LinkedIn photo cache hits (slug-keyed)",
)

tier1_cache_misses_total = Counter(
    "tier1_cache_misses_total",
    "LinkedIn photo cache misses requiring browser scrape",
)

tier1_scrape_total = Counter(
    "tier1_scrape_total",
    "LinkedIn photo scrape attempts by outcome",
    ["outcome"],
)

tier1_upload_total = Counter(
    "tier1_upload_total",
    "LinkedIn photo R2/local uploads by result",
    ["result"],
)
