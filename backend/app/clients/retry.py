from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

import httpx

T = TypeVar("T")

_TRANSIENT_STATUS = frozenset({502, 503, 504})


def is_transient_http_error(exc: BaseException) -> bool:
    if isinstance(exc, (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout, httpx.PoolTimeout)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in _TRANSIENT_STATUS
    return False


async def with_transient_retry(
    operation: Callable[[], Awaitable[T]],
    *,
    max_retries: int = 2,
    base_delay_seconds: float = 0.25,
) -> T:
    """Retry transient HTTP failures with bounded exponential backoff."""
    attempt = 0
    while True:
        try:
            return await operation()
        except Exception as exc:
            if attempt >= max_retries or not is_transient_http_error(exc):
                raise
            await asyncio.sleep(base_delay_seconds * (2**attempt))
            attempt += 1
