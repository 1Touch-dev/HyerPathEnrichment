"""Record HTTP golden-signal metrics for Prometheus scrapes."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.observability.http_metrics import observe_http_request

_SKIP_PATHS = frozenset({"/metrics"})


class HttpMetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.url.path in _SKIP_PATHS:
            return await call_next(request)
        start = time.perf_counter()
        response = await call_next(request)
        observe_http_request(request.method, response.status_code, time.perf_counter() - start)
        return response
