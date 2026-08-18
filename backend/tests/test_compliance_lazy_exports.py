"""Tests for app.compliance's lazy attribute exports (`__getattr__`)."""

from __future__ import annotations

import pytest

from app import compliance


def test_log_event_lazy_import() -> None:
    from app.compliance.audit import log_event

    assert compliance.log_event is log_event


def test_identifier_helpers_lazy_import() -> None:
    from app.compliance.identifiers import (
        hash_identifier,
        hashes_from_request,
        normalize_identifier,
    )

    assert compliance.hash_identifier is hash_identifier
    assert compliance.hashes_from_request is hashes_from_request
    assert compliance.normalize_identifier is normalize_identifier


def test_purge_helpers_lazy_import() -> None:
    from app.compliance.purge import PurgeResult, purge_identifier_data

    assert compliance.PurgeResult is PurgeResult
    assert compliance.purge_identifier_data is purge_identifier_data


def test_unknown_attribute_raises_attribute_error() -> None:
    with pytest.raises(AttributeError, match="has no attribute 'does_not_exist'"):
        _ = compliance.does_not_exist
