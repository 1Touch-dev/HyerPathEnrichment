"""Helpers for asserting shared API success/error envelopes."""

from __future__ import annotations

from typing import Any

from httpx import Response


def assert_success(response: Response, status: int = 200) -> Any:
    body = response.json()
    assert response.status_code == status
    assert body["success"] is True
    assert "data" in body
    assert "meta" in body
    return body["data"]


def assert_error(
    response: Response,
    status: int,
    code: str | None = None,
) -> dict[str, Any]:
    body = response.json()
    assert response.status_code == status
    assert body["success"] is False
    assert "error" in body
    assert body["error"]["status_code"] == status
    assert "message" in body["error"]
    assert "meta" in body
    if code is not None:
        assert body["error"]["code"] == code
    return body
