"""Probe which Gemini model ids work with the current API key."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
for raw in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
    line = raw.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, _, value = line.partition("=")
    os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

MODELS = [
    "gemini-1.5-flash",
    "gemini-1.5-flash-latest",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-flash-latest",
    "gemini-pro-latest",
]


async def main() -> None:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    async with httpx.AsyncClient(timeout=60.0) as client:
        for model in MODELS:
            response = await client.post(
                "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": "Say hi in 3 words"}],
                },
            )
            snippet = response.text[:200].replace("\n", " ")
            print(f"{model}: {response.status_code} {snippet}")


if __name__ == "__main__":
    asyncio.run(main())
