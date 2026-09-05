#!/usr/bin/env python3
"""Check whether OPENAI_API_KEY (backend/.env) is valid and has usable credits.

This calls OpenAI directly with the same key used by `question_generator.py`,
`feedback_generator.py`, and `speech.py` (Whisper) — those call OpenAI
independently of `LLM_MODE`/LiteLLM, so a dead key there fails silently as a
generic "429 Too Many Requests" unless you inspect the response body (see
`app/core/logging.py`'s `_extra_fields`). This script surfaces that body
directly, without needing the backend running.

Usage:
    .venv/bin/python scripts/check_openai_key.py
    .venv/bin/python scripts/check_openai_key.py --model gpt-4o-mini

Exit codes: 0 = key works, 1 = key missing/invalid/out of credits, 2 = network error.
"""

from __future__ import annotations

import argparse
import asyncio

import httpx

from app.core.config import get_settings

CHAT_URL = "https://api.openai.com/v1/chat/completions"
MODELS_URL = "https://api.openai.com/v1/models"

# OpenAI error `code`/`type` values that mean "the key itself is fine, but
# there's no money/quota behind it" — distinct from a real rate limit, and the
# distinction only lives in the response body, not the 429 status code.
_QUOTA_CODES = {"credit_balance_exhausted", "insufficient_quota"}


async def check_key(api_key: str, model: str) -> int:
    if not api_key:
        print("FAIL: OPENAI_API_KEY is not set in backend/.env")
        return 1

    masked = f"{api_key[:10]}...{api_key[-4:]}" if len(api_key) > 14 else "***"
    print(f"Key: {masked}")
    print(f"Model: {model}")
    print()

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            # 1) /v1/models — cheapest way to confirm the key itself is valid
            # (wrong/revoked key -> 401) before spending any tokens.
            resp = await client.get(MODELS_URL, headers={"Authorization": f"Bearer {api_key}"})
            if resp.status_code == 401:
                print("FAIL: 401 Unauthorized — key is invalid or revoked.")
                print(resp.text[:500])
                return 1
            if resp.status_code != 200:
                print(
                    f"WARN: GET /v1/models returned {resp.status_code} (continuing to chat check)"
                )
                print(resp.text[:500])
            else:
                print("OK: key authenticates against /v1/models")

            # 2) A minimal real chat completion — this is what actually
            # exercises billing/quota, which /v1/models does not.
            resp = await client.post(
                CHAT_URL,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": "Reply with just: ok"}],
                    "max_tokens": 5,
                },
            )
    except httpx.ConnectError as exc:
        print(f"FAIL: could not reach api.openai.com ({exc})")
        return 2
    except httpx.TimeoutException:
        print("FAIL: request to OpenAI timed out")
        return 2

    if resp.status_code == 200:
        body = resp.json()
        reply = body["choices"][0]["message"]["content"]
        usage = body.get("usage", {})
        print(f"OK: chat completion succeeded — reply={reply!r}")
        print(f"    tokens used: {usage}")
        return 0

    try:
        error = resp.json().get("error", {})
    except ValueError:
        error = {}
    code = error.get("code") or error.get("type")
    message = error.get("message", resp.text[:300])

    if resp.status_code == 429 and code in _QUOTA_CODES:
        print(f"FAIL: key is valid but OUT OF CREDITS ({code})")
        print(f"    {message}")
        print(
            "    Fix: add billing credits at "
            "https://platform.openai.com/settings/organization/billing"
        )
        return 1
    if resp.status_code == 429:
        print(
            f"FAIL: 429 rate-limited (code={code}) — this is a transient rate limit, retry later."
        )
        print(f"    {message}")
        return 1

    print(f"FAIL: chat completion returned {resp.status_code}")
    print(f"    {message}")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model", default="gpt-4o-mini", help="Model to test the chat completion against"
    )
    parser.add_argument(
        "--key", default=None, help="Override the key instead of reading OPENAI_API_KEY from .env"
    )
    args = parser.parse_args()

    api_key = args.key or get_settings().openai_api_key.strip()
    return asyncio.run(check_key(api_key, args.model))


if __name__ == "__main__":
    raise SystemExit(main())
