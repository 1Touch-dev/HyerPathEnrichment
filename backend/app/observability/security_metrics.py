"""Low-cardinality security and privileged-operation metrics."""

from __future__ import annotations

from typing import Self

try:
    from prometheus_client import Counter
except ImportError:  # pragma: no cover - optional dependency

    class _NoopCounter:
        def labels(self, *_args: object, **_kwargs: object) -> Self:
            return self

        def inc(self, *_args: object, **_kwargs: object) -> None:
            return None

    def Counter(*_args: object, **_kwargs: object) -> _NoopCounter:  # type: ignore[no-redef]
        return _NoopCounter()


authorization_decisions_total = Counter(
    "authorization_decisions_total",
    "Authorization decisions for privileged dependencies",
    ["policy", "decision"],
)

admin_audit_events_total = Counter(
    "admin_audit_events_total",
    "Explicit and fallback admin audit outcomes",
    ["capture", "outcome"],
)

queue_admin_events_total = Counter(
    "queue_admin_events_total",
    "Queue inspection, denial, and redaction events",
    ["operation", "outcome"],
)

_AUTHORIZATION_POLICIES = frozenset({"staff", "permission", "superuser", "queue_retry"})
_AUDIT_CAPTURES = frozenset({"explicit", "fallback"})
_AUDIT_OUTCOMES = frozenset({"success", "failure", "anomaly"})
_QUEUE_OPERATIONS = frozenset({"overview", "failed_jobs", "retry"})
_QUEUE_OUTCOMES = frozenset({"inspected", "redacted", "denied"})


def _bounded(value: object, allowed: frozenset[str]) -> str:
    return value if isinstance(value, str) and value in allowed else "unknown"


def record_authorization(policy: str, *, allowed: bool) -> None:
    """Record a decision using only the dependency's static policy name."""
    authorization_decisions_total.labels(
        policy=_bounded(policy, _AUTHORIZATION_POLICIES),
        decision="allow" if allowed else "deny",
    ).inc()


def record_audit(capture: str, outcome: str, *, count: int = 1) -> None:
    """Record an audit event with values from a closed internal vocabulary."""
    admin_audit_events_total.labels(
        capture=_bounded(capture, _AUDIT_CAPTURES),
        outcome=_bounded(outcome, _AUDIT_OUTCOMES),
    ).inc(count if isinstance(count, int) and count > 0 else 1)


def record_queue_event(operation: str, outcome: str) -> None:
    """Record queue administration using static operation/outcome labels."""
    queue_admin_events_total.labels(
        operation=_bounded(operation, _QUEUE_OPERATIONS),
        outcome=_bounded(outcome, _QUEUE_OUTCOMES),
    ).inc()
