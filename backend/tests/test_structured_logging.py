"""Tests for shared structured logging (JSON + text)."""

from __future__ import annotations

import io
import json
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core import logging as app_logging
from app.core.config import Settings
from app.core.lifespan import lifespan
from app.core.logging import (
    JsonFormatter,
    RequestContextMiddleware,
    configure_logging,
    resolve_log_format,
    set_job_id,
    set_request_id,
)


@pytest.fixture(autouse=True)
def _reset_logging_state() -> None:
    app_logging._configured = False  # noqa: SLF001
    set_request_id(None)
    set_job_id(None)
    yield
    app_logging._configured = False  # noqa: SLF001
    set_request_id(None)
    set_job_id(None)
    logging.getLogger().handlers.clear()


def test_resolve_log_format_defaults_by_env() -> None:
    assert resolve_log_format(Settings(APP_ENV="development", LOG_FORMAT="")) == "text"
    assert resolve_log_format(Settings(APP_ENV="staging", LOG_FORMAT="")) == "json"
    assert resolve_log_format(Settings(APP_ENV="production", LOG_FORMAT="")) == "json"


def test_resolve_log_format_explicit_override() -> None:
    assert resolve_log_format(Settings(APP_ENV="production", LOG_FORMAT="text")) == "text"
    assert resolve_log_format(Settings(APP_ENV="development", LOG_FORMAT="json")) == "json"


def test_json_line_parses_with_required_keys() -> None:
    settings = Settings(
        APP_ENV="development",
        LOG_FORMAT="json",
        LOG_SERVICE="hyrepath-enrichment",
        LOG_LEVEL="INFO",
    )
    configure_logging(settings, force=True)

    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter(service="hyrepath-enrichment"))
    logger = logging.getLogger("tests.structured_logging.json")
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    set_request_id("req-abc")
    set_job_id("job-xyz")
    logger.info("enrichment started")

    line = stream.getvalue().strip()
    payload = json.loads(line)
    assert set(payload) >= {"timestamp", "level", "logger", "message", "service"}
    assert payload["level"] == "INFO"
    assert payload["logger"] == "tests.structured_logging.json"
    assert payload["message"] == "enrichment started"
    assert payload["service"] == "hyrepath-enrichment"
    assert payload["request_id"] == "req-abc"
    assert payload["job_id"] == "job-xyz"
    assert payload["timestamp"].endswith("Z")


def test_text_mode_is_human_readable() -> None:
    settings = Settings(
        APP_ENV="development",
        LOG_FORMAT="text",
        LOG_SERVICE="hyrepath-enrichment",
        LOG_LEVEL="INFO",
    )
    fmt = configure_logging(settings, force=True)
    assert fmt == "text"

    root = logging.getLogger()
    assert root.handlers
    formatter = root.handlers[0].formatter
    assert formatter is not None

    record = logging.LogRecord(
        name="tests.structured_logging.text",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello local",
        args=(),
        exc_info=None,
    )
    set_request_id("req-1")
    rendered = formatter.format(record)
    assert "hello local" in rendered
    assert "INFO" in rendered
    assert "service=hyrepath-enrichment" in rendered
    assert "request_id=req-1" in rendered
    with pytest.raises(json.JSONDecodeError):
        json.loads(rendered)


def test_lifespan_configures_logging_without_error() -> None:
    app = FastAPI(lifespan=lifespan)
    with (
        patch("app.core.lifespan.get_redis_client", return_value=MagicMock()),
        patch("app.core.lifespan.close_redis", new_callable=AsyncMock),
        patch("app.core.lifespan.init_error_tracking"),
        patch("app.core.lifespan.configure_logging", wraps=configure_logging) as wrapped,
    ):
        with TestClient(app):
            pass
        wrapped.assert_called()
        assert app_logging._configured is True  # noqa: SLF001


def test_request_middleware_sets_request_id_header() -> None:
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)

    @app.get("/ping")
    async def ping() -> dict[str, str | None]:
        return {"request_id": app_logging.get_request_id()}

    client = TestClient(app)
    response = client.get("/ping", headers={"X-Request-ID": "client-rid"})
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "client-rid"
    assert response.json()["request_id"] == "client-rid"
