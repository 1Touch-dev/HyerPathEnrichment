"""Canonical OpenAPI error-response contract."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from fastapi.routing import APIRoute

from app.core.openapi import apply_envelope_openapi
from app.main import app

_HTTP_METHODS = {"get", "post", "put", "patch", "delete", "options", "head", "trace"}
_ERROR_ENVELOPE_REF = {"$ref": "#/components/schemas/ErrorResponseEnvelope"}
_BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _operations(schema: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    return [
        (path, method, operation)
        for path, path_item in schema["paths"].items()
        for method, operation in path_item.items()
        if method in _HTTP_METHODS
    ]


def test_every_operation_documents_the_standard_validation_error() -> None:
    """Canonical OpenAPI intentionally advertises the common 422 contract everywhere."""
    operations = _operations(app.openapi())

    assert operations
    assert all("422" in operation["responses"] for _, _, operation in operations)
    for _, _, operation in operations:
        response = operation["responses"]["422"]
        assert response["content"]["application/json"]["schema"] == _ERROR_ENVELOPE_REF


def test_disabled_feature_flag_responses_use_the_standard_error_envelope() -> None:
    feature_flag_operations = [
        operation
        for path, _, operation in _operations(app.openapi())
        if path.startswith("/api/admin/feature-flags") and "405" in operation["responses"]
    ]

    assert len(feature_flag_operations) == 4
    for operation in feature_flag_operations:
        schema = operation["responses"]["405"]["content"]["application/json"]["schema"]
        assert schema == _ERROR_ENVELOPE_REF


def test_queue_retry_405_uses_the_standard_error_envelope() -> None:
    operation = app.openapi()["paths"]["/api/admin/queues/{name}/failed/{job_id}/retry"]["post"]

    assert operation["responses"]["405"]["content"]["application/json"]["schema"] == (
        _ERROR_ENVELOPE_REF
    )


def test_live_openapi_matches_the_offline_canonical_export(client) -> None:
    # Earlier tests temporarily mount probe routes on the shared app and can
    # populate FastAPI's OpenAPI cache while those routes exist. Regenerate
    # from the current registered routes before comparing with a fresh process.
    app.openapi_schema = None
    live_schema = client.get("/openapi.json").json()
    exported = subprocess.run(
        [sys.executable, "scripts/export_openapi.py"],
        cwd=_BACKEND_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert live_schema == json.loads(exported.stdout)


def test_envelope_normalization_is_idempotent() -> None:
    canonical_schema = app.openapi()

    assert apply_envelope_openapi(canonical_schema) == canonical_schema


def test_app_openapi_cache_is_stable() -> None:
    first = app.openapi()
    second = app.openapi()

    assert first is second
    assert first is app.openapi_schema


def test_documented_operations_exactly_match_registered_api_routes() -> None:
    documented = [(path, method) for path, method, _ in _operations(app.openapi())]
    registered = [
        (route.path, method.lower())
        for route in app.routes
        if isinstance(route, APIRoute)
        for method in route.methods
    ]

    assert len(documented) == len(set(documented))
    assert len(registered) == len(set(registered))
    assert set(documented) == set(registered)


def test_operation_ids_are_present_and_unique() -> None:
    operation_ids = [operation["operationId"] for _, _, operation in _operations(app.openapi())]

    assert operation_ids
    assert all(isinstance(operation_id, str) and operation_id for operation_id in operation_ids)
    assert len(operation_ids) == len(set(operation_ids))
