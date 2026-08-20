"""Unit tests for JobMatchingService's helper functions (Module 4, Module B)."""

from __future__ import annotations

import pytest

from app.core.errors import NotFoundError
from app.modules.job_matching.service import _validate_redirect_scheme


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "data:text/html,<script>alert(1)</script>",
        "/relative/path",
        "ftp://example.com/file",
        "",
    ],
)
def test_validate_redirect_scheme_rejects_non_http_schemes(url: str) -> None:
    with pytest.raises(NotFoundError):
        _validate_redirect_scheme(url)


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com/jobs/123",
        "https://linkedin.com/jobs/view/456",
        "https://example.com:8080/path?query=1",
    ],
)
def test_validate_redirect_scheme_accepts_http_and_https(url: str) -> None:
    _validate_redirect_scheme(url)  # must not raise
