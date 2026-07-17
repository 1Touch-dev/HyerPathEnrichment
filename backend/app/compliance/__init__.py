"""LGPD/GDPR/CCPA compliance helpers — identifier hashing, audit trail, data purge."""

from __future__ import annotations

from typing import Any

__all__ = [
    "PurgeResult",
    "hash_identifier",
    "hashes_from_request",
    "log_event",
    "normalize_identifier",
    "purge_identifier_data",
]


def __getattr__(name: str) -> Any:
    if name == "log_event":
        from app.compliance.audit import log_event

        return log_event
    if name in {"hash_identifier", "hashes_from_request", "normalize_identifier"}:
        from app.compliance import identifiers

        return getattr(identifiers, name)
    if name in {"PurgeResult", "purge_identifier_data"}:
        from app.compliance import purge

        return getattr(purge, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
