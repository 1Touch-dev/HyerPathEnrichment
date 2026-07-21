#!/usr/bin/env python3
"""Probe API health and POST to NOTIFY_WEBHOOK_URL on failure (no PII).

Env:
  BASE_URL              — API root (default http://localhost:8000)
  NOTIFY_WEBHOOK_URL    — webhook; no-op when unset (via app settings)
  HEALTH_ALERT_TIMEOUT  — per-request seconds (default 10)
  QUEUE_DEPTH_WARN      — queued job warn threshold (default 100)
  QUEUE_FAILED_WARN     — failed job warn threshold (default 5)
  DRY_RUN               — if 1, probe only and print; never POST

Exit codes:
  0 — probes healthy (and queue under thresholds), or alert sent / dry-run ok
  1 — probe/queue failure and webhook unset or POST failed
  2 — usage / unexpected error

Example cron (every 2 minutes):
  */2 * * * * cd /opt/hyrepath/HyerPathEnrichment/backend && \\
    .venv/bin/python scripts/health_alert_notify.py >> /var/log/hyrepath-health-alert.log 2>&1
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

# Allow `python scripts/health_alert_notify.py` from backend/ or repo root.
_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    return int(raw)


async def _amain(args: argparse.Namespace) -> int:
    from app.observability.health_alerts import (
        notify_on_health_failure,
        probe_health_endpoints,
        queue_depth_snapshot,
    )

    base_url = args.base_url.rstrip("/")
    probes = await probe_health_endpoints(base_url, timeout=args.timeout)
    queue = queue_depth_snapshot()

    for probe in probes:
        status = "PASS" if probe.ok else "FAIL"
        print(f"{status}  {probe.path} reason={probe.reason} status={probe.status_code}")

    if queue is not None:
        print(f"INFO  queue queued={queue['queued']} failed={queue['failed']}")
    else:
        print("INFO  queue snapshot unavailable")

    failures = [p for p in probes if not p.ok]
    queue_alert = False
    if queue is not None and (
        queue["queued"] >= args.queue_depth_warn or queue["failed"] >= args.queue_failed_warn
    ):
        queue_alert = True

    if not failures and not queue_alert:
        print("PASS  all checks ok")
        return 0

    if args.dry_run:
        print("DRY_RUN  would notify NOTIFY_WEBHOOK_URL (no POST)")
        return 0

    sent = await notify_on_health_failure(
        base_url,
        timeout=args.timeout,
        queue_depth_warn=args.queue_depth_warn,
        queue_failed_warn=args.queue_failed_warn,
    )
    if sent:
        print("PASS  ops alert posted")
        return 0
    print("FAIL  alert needed but webhook unset or POST failed", file=sys.stderr)
    return 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        default=os.environ.get("BASE_URL", "http://localhost:8000"),
        help="API base URL",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=float(os.environ.get("HEALTH_ALERT_TIMEOUT", "10")),
    )
    parser.add_argument(
        "--queue-depth-warn",
        type=int,
        default=_env_int("QUEUE_DEPTH_WARN", 100),
    )
    parser.add_argument(
        "--queue-failed-warn",
        type=int,
        default=_env_int("QUEUE_FAILED_WARN", 5),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=os.environ.get("DRY_RUN", "").strip().lower() in {"1", "true", "yes"},
    )
    args = parser.parse_args()
    try:
        raise SystemExit(asyncio.run(_amain(args)))
    except SystemExit:
        raise
    except Exception as exc:  # pragma: no cover - CLI guard
        print(f"FAIL  {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
