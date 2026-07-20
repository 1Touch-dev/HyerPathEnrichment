"""Unit tests for backend/scripts/smoke_test.py (no live API required)."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "smoke_test.py"


def _mock_response(status_code: int, json_data: dict) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.text = str(json_data)
    return resp


def _success(data: dict) -> dict:
    return {"success": True, "data": data, "message": None, "meta": None}


def _dossier() -> dict:
    return {
        "handles": [{"platform": "X", "username": "smoke-user"}],
        "confidence": 0.5,
        "sources": [],
        "metadata": {},
    }


def _load_smoke(monkeypatch: pytest.MonkeyPatch, skip_async: str = "") -> object:
    monkeypatch.setenv("SMOKE_SKIP_ASYNC", skip_async)
    spec = importlib.util.spec_from_file_location("smoke_test", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@patch("requests.post")
@patch("requests.get")
def test_smoke_async_polls_until_completed(
    mock_get: MagicMock,
    mock_post: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    smoke = _load_smoke(monkeypatch)

    mock_post.side_effect = [
        _mock_response(401, {}),
        _mock_response(200, _success({"status": "completed", "dossier": _dossier()})),
        _mock_response(202, _success({"status": "accepted"})),
        _mock_response(201, _success({"id": "dsar-1"})),
        _mock_response(202, _success({"status": "queued", "id": "job-123"})),
    ]
    mock_get.side_effect = [
        _mock_response(200, _success({"status": "ok", "service": "test"})),
        _mock_response(200, _success({"status": "ready"})),
        _mock_response(200, _success({"status": "running"})),
        _mock_response(200, _success({"status": "completed", "dossier": _dossier()})),
    ]

    with patch.object(smoke.time, "sleep"):
        smoke.main()

    assert mock_post.call_count == 5
    assert mock_get.call_count == 4
    assert mock_get.call_args_list[-1][0][0].endswith("/enrich/job-123")


@patch("requests.post")
@patch("requests.get")
def test_smoke_skip_async(
    mock_get: MagicMock,
    mock_post: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    smoke = _load_smoke(monkeypatch, skip_async="1")

    mock_get.side_effect = [
        _mock_response(200, _success({"status": "ok", "service": "test"})),
        _mock_response(200, _success({"status": "ready"})),
    ]
    mock_post.side_effect = [
        _mock_response(401, {}),
        _mock_response(200, _success({"status": "completed", "dossier": _dossier()})),
        _mock_response(202, _success({"status": "accepted"})),
        _mock_response(201, _success({"id": "dsar-1"})),
    ]

    smoke.main()

    assert mock_post.call_count == 4
    assert mock_get.call_count == 2
