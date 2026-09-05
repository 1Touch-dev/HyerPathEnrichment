"""Post-process OpenAPI schema to document runtime success/error envelopes."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from fastapi import FastAPI

_ERROR_RESPONSE_REF = "#/components/schemas/ErrorResponseEnvelope"
_DEFAULT_ERROR_STATUS_CODES = ("400", "401", "403", "404", "409", "422", "429", "500", "503")


def _success_response_schema(data_schema: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["success", "data"],
        "properties": {
            "success": {"type": "boolean", "const": True},
            "data": data_schema,
            "message": {"anyOf": [{"type": "string"}, {"type": "null"}]},
            "meta": {
                "anyOf": [
                    {"type": "object", "additionalProperties": True},
                    {"type": "null"},
                ],
            },
        },
    }


def _error_response_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["success", "error"],
        "properties": {
            "success": {"type": "boolean", "const": False},
            "error": {
                "type": "object",
                "required": ["code", "message", "status_code"],
                "properties": {
                    "code": {"type": "string"},
                    "message": {"type": "string"},
                    "details": {},
                    "status_code": {"type": "integer"},
                },
            },
            "meta": {
                "anyOf": [
                    {"type": "object", "additionalProperties": True},
                    {"type": "null"},
                ],
            },
        },
    }


def _error_response_documentation(response: dict[str, Any] | None = None) -> dict[str, Any]:
    documented = deepcopy(response) if response is not None else {}
    documented.setdefault("description", "Error response envelope")
    content = documented.setdefault("content", {})
    if not isinstance(content, dict):
        content = {}
        documented["content"] = content
    json_content = content.setdefault("application/json", {})
    if not isinstance(json_content, dict):
        json_content = {}
        content["application/json"] = json_content
    json_content["schema"] = {"$ref": _ERROR_RESPONSE_REF}
    return documented


def apply_envelope_openapi(schema: dict[str, Any]) -> dict[str, Any]:
    """Wrap JSON success responses and attach standard error responses."""
    updated = deepcopy(schema)
    components = updated.setdefault("components", {})
    schemas = components.setdefault("schemas", {})
    schemas.setdefault("SuccessResponseEnvelope", _success_response_schema({"type": "object"}))
    schemas["ErrorResponseEnvelope"] = _error_response_schema()

    for path_item in updated.get("paths", {}).values():
        if not isinstance(path_item, dict):
            continue
        for operation in path_item.values():
            if not isinstance(operation, dict):
                continue
            responses = operation.get("responses")
            if not isinstance(responses, dict):
                continue

            for status_code, response in list(responses.items()):
                if not str(status_code).startswith("2"):
                    continue
                if not isinstance(response, dict):
                    continue
                content = response.get("content")
                if not isinstance(content, dict):
                    continue
                json_content = content.get("application/json")
                if not isinstance(json_content, dict):
                    continue
                inner_schema = json_content.get("schema")
                if not isinstance(inner_schema, dict):
                    continue
                if not (
                    inner_schema.get("required") == ["success", "data"]
                    and isinstance(inner_schema.get("properties"), dict)
                    and "data" in inner_schema["properties"]
                ):
                    json_content["schema"] = _success_response_schema(deepcopy(inner_schema))

            for status_code in _DEFAULT_ERROR_STATUS_CODES:
                response = responses.get(status_code)
                if response is None or status_code == "422":
                    responses[status_code] = _error_response_documentation(
                        response if isinstance(response, dict) else None
                    )

            response_405 = responses.get("405")
            if isinstance(response_405, dict):
                responses["405"] = _error_response_documentation(response_405)

    return updated


def install_envelope_openapi(app: FastAPI) -> None:
    """Make the live app and offline exports share the canonical OpenAPI schema."""
    original_openapi = app.openapi

    def envelope_openapi() -> dict[str, Any]:
        if app.openapi_schema is None:
            app.openapi_schema = apply_envelope_openapi(original_openapi())
        return app.openapi_schema

    app.openapi = envelope_openapi  # type: ignore[method-assign]
