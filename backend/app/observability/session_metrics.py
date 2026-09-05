"""Prometheus metrics for session tracking."""

from prometheus_client import Counter, Gauge, Histogram

# Session lifecycle metrics
sessions_created_total = Counter(
    "sessions_created_total",
    "Total number of practice sessions created",
    ["session_type"],
)

sessions_completed_total = Counter(
    "sessions_completed_total",
    "Total number of sessions completed",
    ["session_type", "status"],
)

session_duration_seconds = Histogram(
    "session_duration_seconds",
    "Duration of completed sessions in seconds",
    ["session_type"],
    buckets=[60, 300, 600, 1200, 1800, 3600, 7200],
)

# Question attempt metrics
attempts_created_total = Counter(
    "attempts_created_total",
    "Total number of question attempts",
    ["response_type"],
)

attempt_score_distribution = Histogram(
    "attempt_score_distribution",
    "Distribution of AI scores for attempts",
    buckets=[0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
)

# Active session tracking
active_sessions = Gauge(
    "active_sessions_current",
    "Current number of active (in_progress) sessions",
)

# State transition tracking
state_transitions_total = Counter(
    "state_transitions_total",
    "Total number of session state transitions",
    ["from_state", "to_state"],
)
