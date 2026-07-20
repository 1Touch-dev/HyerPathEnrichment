"""APIRoute that wraps successful JSON responses in SuccessResponse."""

from __future__ import annotations

import json
from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import Request, Response
from fastapi.routing import APIRoute
from starlette.responses import JSONResponse, Response as StarletteResponse

from app.core.responses import success_envelope


def _already_enveloped(payload: Any) -> bool:
    return isinstance(payload, dict) and "success" in payload and (
        ("data" in payload) or ("error" in payload)
    )


def _is_json_response(response: StarletteResponse) -> bool:
    media_type = (response.media_type or "").lower()
    if "json" in media_type:
        return True
    content_type = response.headers.get("content-type", "").lower()
    return "application/json" in content_type


class EnvelopeAPIRoute(APIRoute):
    """Wrap successful JSON handler results in the shared success envelope."""

    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        original = super().get_route_handler()

        async def envelope_handler(request: Request) -> Response:
            response = await original(request)
            if response.status_code >= 400:
                return response
            if not _is_json_response(response):
                return response

            raw = getattr(response, "body", None) or b""
            if not raw:
                return response

            try:
                payload = json.loads(raw)
            except (json.JSONDecodeError, TypeError, UnicodeDecodeError):
                return response

            if _already_enveloped(payload):
                return response

            headers = {
                key: value
                for key, value in response.headers.items()
                if key.lower() != "content-length"
            }
            return JSONResponse(
                content=success_envelope(payload),
                status_code=response.status_code,
                headers=headers,
            )

        return envelope_handler
