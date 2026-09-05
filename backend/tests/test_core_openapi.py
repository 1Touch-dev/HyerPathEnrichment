"""Tests for OpenAPI envelope post-processing (app.core.openapi)."""

from __future__ import annotations

from app.core.openapi import apply_envelope_openapi


def test_wraps_2xx_json_responses_in_success_envelope() -> None:
    schema = {
        "paths": {
            "/widgets": {
                "get": {
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {"type": "array", "items": {"type": "object"}}
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    updated = apply_envelope_openapi(schema)

    wrapped = updated["paths"]["/widgets"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]
    assert wrapped["required"] == ["success", "data"]
    assert wrapped["properties"]["data"] == {"type": "array", "items": {"type": "object"}}
    assert wrapped["properties"]["success"]["const"] is True


def test_registers_success_and_error_envelope_schemas() -> None:
    schema = {"paths": {}}

    updated = apply_envelope_openapi(schema)

    schemas = updated["components"]["schemas"]
    assert "SuccessResponseEnvelope" in schemas
    error_schema = schemas["ErrorResponseEnvelope"]
    assert error_schema["required"] == ["success", "error"]
    assert set(error_schema["properties"]["error"]["required"]) == {
        "code",
        "message",
        "status_code",
    }


def test_adds_error_envelope_refs_for_missing_status_codes() -> None:
    schema = {
        "paths": {
            "/widgets": {
                "post": {
                    "responses": {
                        "201": {"content": {"application/json": {"schema": {"type": "object"}}}}
                    }
                }
            }
        }
    }

    updated = apply_envelope_openapi(schema)

    responses = updated["paths"]["/widgets"]["post"]["responses"]
    for status_code in ("400", "401", "403", "404", "409", "422", "429", "500", "503"):
        assert responses[status_code]["content"]["application/json"]["schema"] == {
            "$ref": "#/components/schemas/ErrorResponseEnvelope"
        }


def test_leaves_existing_error_response_untouched() -> None:
    schema = {
        "paths": {
            "/widgets": {
                "get": {
                    "responses": {
                        "404": {"description": "custom not found"},
                    }
                }
            }
        }
    }

    updated = apply_envelope_openapi(schema)

    # Custom 404 already present is not overwritten with the generic envelope ref.
    assert updated["paths"]["/widgets"]["get"]["responses"]["404"] == {
        "description": "custom not found"
    }


def test_skips_non_dict_and_non_2xx_entries_without_raising() -> None:
    schema = {
        "paths": {
            "/widgets": {
                "parameters": ["not-a-dict-operation"],
                "get": {
                    "responses": {
                        "304": {"description": "not modified"},
                        "500": "not-a-dict-response",
                    }
                },
            },
            "/legacy": "not-a-dict-path-item",
        }
    }

    updated = apply_envelope_openapi(schema)

    responses = updated["paths"]["/widgets"]["get"]["responses"]
    # 304 is a 3xx response, left untouched (not wrapped as a success envelope).
    assert responses["304"] == {"description": "not modified"}
    # Non-dict response for an already-present status code is left untouched.
    assert responses["500"] == "not-a-dict-response"
    assert updated["paths"]["/legacy"] == "not-a-dict-path-item"


def test_skips_operations_missing_responses_or_content() -> None:
    schema = {
        "paths": {
            "/widgets": {
                "get": {"responses": "not-a-dict"},
                "post": {"responses": {"200": {"description": "no content key"}}},
                "put": {"responses": {"200": {"content": {"application/json": "not-a-dict"}}}},
                "patch": {
                    "responses": {
                        "200": {"content": {"application/json": {"schema": "not-a-dict"}}}
                    }
                },
            }
        }
    }

    updated = apply_envelope_openapi(schema)

    # None of these malformed shapes should raise; envelope wrapping is simply skipped.
    assert updated["paths"]["/widgets"]["get"]["responses"] == "not-a-dict"
    assert "content" not in updated["paths"]["/widgets"]["post"]["responses"]["200"]
