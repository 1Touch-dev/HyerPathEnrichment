from typing import Any

import httpx
import pytest

from scripts import e2e_realworld_strict as strict


class _Response:
    def __init__(
        self,
        status_code: int,
        payload: dict[str, Any],
        *,
        cookies: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self._payload = payload
        self.cookies = httpx.Cookies(cookies)

    def json(self) -> dict[str, Any]:
        return self._payload


def test_unwrap_data_supports_shared_envelope_and_legacy_payload() -> None:
    data = {"status": "ok"}

    assert strict._unwrap_data({"success": True, "data": data}) == data
    assert strict._unwrap_data(data) == data


@pytest.mark.asyncio
async def test_sync_probe_logs_in_and_parses_enveloped_response(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, url: str, **kwargs: Any) -> _Response:
            if url.endswith("/auth/login"):
                return _Response(
                    200, {"success": True, "data": {}}, cookies={"access_token": "jwt"}
                )
            assert kwargs["headers"]["Cookie"] == "access_token=jwt"
            return _Response(
                200,
                {
                    "success": True,
                    "data": {
                        "status": "completed",
                        "dossier": {
                            "handles": [{"platform": "GitHub", "username": "torvalds"}],
                            "emails": [],
                            "business": {"name": "Coffee"},
                        },
                    },
                },
            )

    monkeypatch.setenv("E2E_USER_EMAIL", "verified@example.com")
    monkeypatch.setenv("E2E_USER_PASSWORD", "VerifiedPassword123")
    monkeypatch.setattr(strict.httpx, "AsyncClient", lambda **_kwargs: _Client())
    monkeypatch.setattr(strict, "RESULTS_DIR", tmp_path)

    probe = strict.StrictProbe()
    await probe.check_api_sync_paths()

    assert [result.name for result in probe.results] == [
        "api_cookie_auth",
        "api_sync_completed",
        "api_sync_has_handles_or_emails",
        "api_sync_business_optional",
    ]
    assert all(result.ok for result in probe.results)
