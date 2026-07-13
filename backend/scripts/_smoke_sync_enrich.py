"""Smoke: sync enrich tier2+tier4 using container API_TOKEN."""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request


def main() -> int:
    token = os.environ["API_TOKEN"]
    body = json.dumps(
        {
            "username": "torvalds",
            "business": "coffee shop San Francisco",
            "requested_tiers": ["tier2", "tier4"],
        }
    ).encode()
    req = urllib.request.Request(
        "http://127.0.0.1:8000/enrich/sync",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=360) as resp:
            raw = resp.read().decode()
            code = resp.status
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        code = exc.code
    except Exception as exc:  # noqa: BLE001
        print(f"REQUEST_ERROR {type(exc).__name__}: {exc}")
        return 2

    print(f"HTTP {code}")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        print(raw[:800])
        return 1

    print(f"status {data.get('status')}")
    dossier = data.get("dossier") or {}
    sources = dossier.get("sources") or []
    handles = dossier.get("handles") or []
    print(f"sources {sources}")
    print(f"handles_count {len(handles)}")
    if handles:
        sample = [
            {k: h.get(k) for k in ("platform", "username", "profile_url", "confidence")}
            for h in handles[:2]
        ]
        print(f"sample_handles {sample}")
    print(f"business {dossier.get('business')}")
    print(f"jobs_count {len(dossier.get('jobs') or [])}")
    for name in (
        "Social Analyzer",
        "Google Maps Scraper",
        "Sherlock",
        "Maigret",
        "JobSpy",
    ):
        print(f"in_sources[{name}]={name in sources}")

    summary = {
        "http": code,
        "status": data.get("status"),
        "sources": sources,
        "handles_count": len(handles),
        "business": dossier.get("business"),
        "jobs_count": len(dossier.get("jobs") or []),
        "error": data.get("error") or data.get("detail"),
    }
    print(json.dumps(summary, indent=2))
    return 0 if code == 200 else 1


if __name__ == "__main__":
    sys.exit(main())
