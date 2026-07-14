"""POST a chat completion to local LiteLLM and print the response."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

body = {
    "model": "gemini/gemini-2.5-flash",
    "messages": [{"role": "user", "content": "say hi"}],
}
req = urllib.request.Request(
    "http://127.0.0.1:4000/v1/chat/completions",
    data=json.dumps(body).encode(),
    headers={"Content-Type": "application/json"},
    method="POST",
)
try:
    with urllib.request.urlopen(req, timeout=90) as resp:
        print(resp.read().decode()[:800])
except urllib.error.HTTPError as exc:
    print("HTTP", exc.code, exc.read().decode()[:800])
    raise
