"""Run k6 load tests against the Docker Compose API (Windows-safe).

Brings up the free stack with fake sidecars + loadtest rate-limit override,
waits for /health, runs grafana/k6 against the compose network, and writes
backend/.e2e-results/load-report.json.

Env:
  BASE_URL          — override API URL for k6 (default http://api:8000 on compose net)
  API_TOKEN         — Bearer token (default change-me)
  LOAD_PROFILE      — smoke | full (default smoke)
  LOAD_KEEP_STACK   — set to 1 to leave compose stack running
  LOAD_SKIP_UP      — set to 1 to skip compose up (stack already running)
  K6_IMAGE          — k6 image (default grafana/k6:v0.54.0)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPOSE_DIR = ROOT / "docker"
K6_SCRIPT = ROOT / "load" / "k6" / "main.js"
RESULTS = ROOT / ".e2e-results"
REPORT_PATH = RESULTS / "load-report.json"
SUMMARY_PATH = RESULTS / "k6-summary.json"

API_TOKEN = os.environ.get("API_TOKEN", "change-me")
LOAD_PROFILE = os.environ.get("LOAD_PROFILE", "smoke")
K6_IMAGE = os.environ.get("K6_IMAGE", "grafana/k6:0.54.0")
KEEP_STACK = os.environ.get("LOAD_KEEP_STACK", "0") == "1"
SKIP_UP = os.environ.get("LOAD_SKIP_UP", "0") == "1"
# Host-side health wait uses published port; k6 inside Docker uses service DNS.
HOST_HEALTH_URL = os.environ.get("LOAD_HEALTH_URL", "http://127.0.0.1:8000/health")
K6_BASE_URL = os.environ.get("BASE_URL", "http://api:8000")

COMPOSE = [
    "docker",
    "compose",
    "--profile",
    "paid",
    "-f",
    "docker-compose.yml",
    "-f",
    "docker-compose.fake-sidecars.yml",
    "-f",
    "docker-compose.loadtest.yml",
]

STACK_SERVICES = [
    "api",
    "worker",
    "redis",
    "postgres",
    "social-analyzer",
    "google-maps-scraper",
    "email-verifier",
    "reacher",
]


def run(
    cmd: list[str], *, cwd: Path | None = None, check: bool = True
) -> subprocess.CompletedProcess[str]:
    print("+", " ".join(cmd), flush=True)
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        text=True,
        check=check,
        capture_output=False,
    )


def http_status(url: str) -> int | None:
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            return int(resp.status)
    except (urllib.error.URLError, TimeoutError, ValueError, OSError, ConnectionError):
        return None


def wait_for_health(*, attempts: int = 90, interval: float = 2.0) -> None:
    for i in range(attempts):
        code = http_status(HOST_HEALTH_URL)
        if code == 200:
            print(f"PASS  {HOST_HEALTH_URL} → 200", flush=True)
            return
        print(f"wait  health={code} ({i + 1}/{attempts})", flush=True)
        time.sleep(interval)
    raise SystemExit(f"API health never returned 200 at {HOST_HEALTH_URL}")


def api_network_name() -> str:
    ps = subprocess.run(
        COMPOSE + ["ps", "-q", "api"],
        cwd=str(COMPOSE_DIR),
        text=True,
        capture_output=True,
        check=True,
    )
    container_id = (ps.stdout or "").strip().splitlines()
    if not container_id:
        raise SystemExit("api container not running — start the loadtest stack first")
    inspect = subprocess.run(
        [
            "docker",
            "inspect",
            "-f",
            "{{range $k, $v := .NetworkSettings.Networks}}{{$k}}\n{{end}}",
            container_id[0],
        ],
        text=True,
        capture_output=True,
        check=True,
    )
    networks = [line.strip() for line in (inspect.stdout or "").splitlines() if line.strip()]
    if not networks:
        raise SystemExit("could not resolve compose network for api container")
    return networks[0]


def run_k6(network: str) -> int:
    RESULTS.mkdir(parents=True, exist_ok=True)
    if SUMMARY_PATH.exists():
        SUMMARY_PATH.unlink()

    # Mount script dir; write summary to a bind-mounted results dir.
    script_mount = str(K6_SCRIPT.parent.resolve())
    results_mount = str(RESULTS.resolve())

    cmd = [
        "docker",
        "run",
        "--rm",
        "--network",
        network,
        "-e",
        f"BASE_URL={K6_BASE_URL}",
        "-e",
        f"API_TOKEN={API_TOKEN}",
        "-e",
        f"LOAD_PROFILE={LOAD_PROFILE}",
        "-v",
        f"{script_mount}:/scripts:ro",
        "-v",
        f"{results_mount}:/results",
        K6_IMAGE,
        "run",
        "--summary-export=/results/k6-summary.json",
        "/scripts/main.js",
    ]
    print("+", " ".join(cmd), flush=True)
    proc = subprocess.run(cmd, text=True, check=False)
    return int(proc.returncode)


def write_report(k6_exit: int) -> dict:
    summary: dict = {}
    if SUMMARY_PATH.is_file():
        try:
            summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            summary = {"parse_error": str(exc)}

    metrics = summary.get("metrics") or {}

    # k6 --summary-export: under metrics.*.thresholds, boolean true means threshold
    # was *crossed* (failed). Newer exports may use {"ok": true/false}.
    threshold_results: dict[str, bool] = {}
    for name, payload in metrics.items():
        th = payload.get("thresholds") if isinstance(payload, dict) else None
        if not isinstance(th, dict):
            continue
        for th_name, val in th.items():
            key = f"{name}{{{th_name}}}"
            if isinstance(val, dict) and "ok" in val:
                threshold_results[key] = bool(val["ok"])
            elif isinstance(val, bool):
                threshold_results[key] = not val  # true = crossed = failed

    root_thresholds = summary.get("thresholds")
    if isinstance(root_thresholds, dict) and root_thresholds:
        threshold_results = {}
        for key, val in root_thresholds.items():
            if isinstance(val, dict) and "ok" in val:
                threshold_results[key] = bool(val["ok"])
            elif isinstance(val, bool):
                threshold_results[key] = val

    # Exit code is the source of truth when thresholds are configured in the script.
    all_ok = k6_exit == 0
    report = {
        "tool": "k6",
        "profile": LOAD_PROFILE,
        "base_url": K6_BASE_URL,
        "k6_exit_code": k6_exit,
        "thresholds_passed": all_ok and k6_exit == 0,
        "threshold_results": threshold_results,
        "report_path": str(REPORT_PATH.as_posix()),
        "summary_path": str(SUMMARY_PATH.as_posix()),
        "metrics_sample": {
            key: metrics[key]
            for key in (
                "http_req_duration",
                "http_req_failed",
                "enrich_enqueue_ok",
                "enrich_job_completed",
                "enrich_sync_ok",
            )
            if key in metrics
        },
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {REPORT_PATH}", flush=True)
    return report


def main() -> int:
    if not K6_SCRIPT.is_file():
        raise SystemExit(f"missing k6 script: {K6_SCRIPT}")

    RESULTS.mkdir(parents=True, exist_ok=True)
    try:
        if not SKIP_UP:
            env = os.environ.copy()
            env.setdefault("DOCKER_BUILDKIT", "0")
            env.setdefault("COMPOSE_DOCKER_CLI_BUILD", "0")
            # Parallel classic builds of the same fake-sidecar tag can race (AlreadyExists).
            env.setdefault("COMPOSE_PARALLEL_LIMIT", "1")
            print(
                "== bringing up loadtest stack (fake sidecars + elevated rate limits) ==",
                flush=True,
            )
            subprocess.run(
                COMPOSE + ["build", "social-analyzer", "api", "worker"],
                cwd=str(COMPOSE_DIR),
                check=True,
                env=env,
            )
            subprocess.run(
                COMPOSE + ["up", "-d", "--no-build", *STACK_SERVICES],
                cwd=str(COMPOSE_DIR),
                check=True,
                env=env,
            )

        wait_for_health()
        network = api_network_name()
        print(f"Using compose network: {network}", flush=True)
        k6_exit = run_k6(network)
        report = write_report(k6_exit)

        if k6_exit != 0 or not report.get("thresholds_passed"):
            print("FAIL  load test thresholds or k6 exit", file=sys.stderr, flush=True)
            return 1
        print("PASS  load test", flush=True)
        return 0
    finally:
        if not KEEP_STACK and not SKIP_UP:
            subprocess.run(COMPOSE + ["down"], cwd=str(COMPOSE_DIR), check=False)


if __name__ == "__main__":
    raise SystemExit(main())
