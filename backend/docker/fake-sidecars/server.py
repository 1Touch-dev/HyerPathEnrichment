"""Lightweight HTTP mocks for AGPL/heavy sidecars used in CI integration tests."""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, Response
from starlette.routing import Route

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
GMAPS_JOBS: dict[str, dict[str, Any]] = {}


def _load_json(name: str) -> Any:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


def _load_text(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


async def social_get_settings(_: Request) -> JSONResponse:
    return JSONResponse({"websites": ["GitHub", "Twitter"]})


async def social_analyze_string(_: Request) -> JSONResponse:
    return JSONResponse(_load_json("social_analyzer_analyze_string.json"))


async def gmaps_create_job(_: Request) -> JSONResponse:
    job_id = str(uuid.uuid4())
    GMAPS_JOBS[job_id] = {"status": "ok"}
    return JSONResponse({"id": job_id})


async def gmaps_job_status(request: Request) -> JSONResponse:
    job_id = request.path_params["job_id"]
    if job_id not in GMAPS_JOBS:
        return JSONResponse({"status": "failed"}, status_code=404)
    return JSONResponse({"status": "ok"})


async def gmaps_job_download(request: Request) -> PlainTextResponse:
    job_id = request.path_params["job_id"]
    if job_id not in GMAPS_JOBS:
        return PlainTextResponse("", status_code=404)
    return PlainTextResponse(_load_text("gmaps_job.csv"))


async def reacher_check_email(request: Request) -> JSONResponse:
    body: dict[str, Any] = {}
    try:
        parsed = await request.json()
        if isinstance(parsed, dict):
            body = parsed
    except Exception:
        body = {}
    to_email = str(body.get("to_email", "")).lower()
    # Addresses containing "catchall" simulate accept-all domains (low trust).
    if "catchall" in to_email.replace("-", "").replace("_", ""):
        return JSONResponse(
            {
                "is_reachable": "risky",
                "misc": {"is_catch_all": True, "is_disposable": False},
                "smtp": {
                    "can_connect_smtp": True,
                    "is_catch_all": True,
                    "is_deliverable": True,
                },
            }
        )
    return JSONResponse(
        {
            "is_reachable": "safe",
            "misc": {"is_catch_all": False, "is_disposable": False},
            "smtp": {
                "can_connect_smtp": True,
                "is_catch_all": False,
                "is_deliverable": True,
            },
        }
    )


async def email_verification(request: Request) -> JSONResponse:
    return JSONResponse(
        {
            "syntax": {"valid": True},
            "reachable": "yes",
            "has_mx_records": True,
        }
    )


async def health(_: Request) -> Response:
    return Response(status_code=200)


def build_app() -> Starlette:
    mode = os.environ.get("FAKE_SIDECAR", "").strip().lower()

    if mode == "social-analyzer":
        routes = [
            Route("/get_settings", social_get_settings, methods=["GET"]),
            Route("/analyze_string", social_analyze_string, methods=["POST"]),
            Route("/health", health, methods=["GET"]),
        ]
    elif mode == "google-maps-scraper":
        routes = [
            Route("/api/v1/jobs", gmaps_create_job, methods=["POST"]),
            Route("/api/v1/jobs/{job_id}", gmaps_job_status, methods=["GET"]),
            Route("/api/v1/jobs/{job_id}/download", gmaps_job_download, methods=["GET"]),
            Route("/health", health, methods=["GET"]),
        ]
    elif mode == "reacher":
        routes = [
            Route("/v1/check_email", reacher_check_email, methods=["POST"]),
            Route("/health", health, methods=["GET"]),
        ]
    elif mode == "email-verifier":
        routes = [
            Route("/v1/{email}/verification", email_verification, methods=["GET"]),
            Route("/health", health, methods=["GET"]),
        ]
    else:
        raise RuntimeError(f"FAKE_SIDECAR must be set; got {mode!r}")

    return Starlette(routes=routes)


app = build_app()
