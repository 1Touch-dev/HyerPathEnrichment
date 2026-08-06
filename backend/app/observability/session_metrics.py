"""Prometheus metrics for practice sessions."""

from prometheus_client import Counter, Histogram

# Session lifecycle metrics
sessions_started_total = Counter(
    "sessions_started_total",
    "Total number of practice sessions started",
    ["session_type"],
)

sessions_completed_total = Counter(
    "sessions_completed_total",
    "Total number of practice sessions completed",
    ["session_type"],
)

sessions_abandoned_total = Counter(
    "sessions_abandoned_total",
    "Total number of practice sessions abandoned",
    ["session_type"],
)

# Session duration metrics
session_duration_seconds = Histogram(
    "session_duration_seconds",
    "Duration of practice sessions in seconds",
    ["session_type"],
    buckets=[60, 300, 600, 1200, 1800, 3600, 7200],  # 1min to 2hrs
)
