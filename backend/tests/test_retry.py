from __future__ import annotations

import httpx
import pytest

from app.clients.retry import is_transient_http_error


def _status_error(status_code: int) -> httpx.HTTPStatusError:
    response = httpx.Response(status_code, request=httpx.Request("GET", "http://example"))
    return httpx.HTTPStatusError("bad", request=response.request, response=response)


@pytest.mark.parametrize("status_code", [429, 502, 503, 504])
def test_is_transient_http_error_detects_transient_statuses(status_code: int) -> None:
    assert is_transient_http_error(_status_error(status_code))


def test_is_transient_http_error_rejects_non_transient_status() -> None:
    assert not is_transient_http_error(_status_error(400))
