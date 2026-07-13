"""One-shot sidecar HTTP probe from inside the worker container."""
from __future__ import annotations

import os
import sys

import httpx


def main() -> int:
    sa = os.environ.get("SOCIAL_ANALYZER_URL", "").strip()
    gm = os.environ.get("GMAPS_SCRAPER_URL", "").strip()
    print(f"SOCIAL_ANALYZER_URL={sa}")
    print(f"GMAPS_SCRAPER_URL={gm}")
    ok = True
    with httpx.Client(timeout=30.0) as client:
        try:
            r1 = client.get(f"{sa.rstrip('/')}/get_settings")
            print(f"worker->SA status={r1.status_code} bytes={len(r1.content)}")
            if r1.status_code != 200:
                ok = False
        except Exception as exc:  # noqa: BLE001
            print(f"worker->SA ERROR: {exc}")
            ok = False
        try:
            r2 = client.get(f"{gm.rstrip('/')}/api/docs")
            print(f"worker->GMaps status={r2.status_code} bytes={len(r2.content)}")
            if r2.status_code != 200:
                ok = False
        except Exception as exc:  # noqa: BLE001
            print(f"worker->GMaps ERROR: {exc}")
            ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
