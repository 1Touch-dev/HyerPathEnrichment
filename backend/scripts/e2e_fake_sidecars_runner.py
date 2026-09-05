"""Run fake-sidecar Docker E2E (Python driver avoids CRLF issues on Windows/WSL)."""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPOSE_DIR = ROOT / "docker"
SCRIPT = ROOT / "scripts" / "e2e_fake_sidecars.py"
RESULTS = ROOT / ".e2e-results"
BASE = "http://localhost:8000"
COMPOSE = [
    "docker",
    "compose",
    "--profile",
    "paid",
    "-f",
    "docker-compose.yml",
    "-f",
    "docker-compose.fake-sidecars.yml",
]


def run(cmd: list[str], *, cwd: Path | None = None, input_text: str | None = None) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        input=input_text,
        text=True,
        check=True,
    )


def curl_code(url: str) -> str:
    result = subprocess.run(
        ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", url],
        capture_output=True,
        text=True,
        check=False,
    )
    return (result.stdout or "").strip()


def main() -> int:
    RESULTS.mkdir(parents=True, exist_ok=True)
    try:
        run(
            COMPOSE
            + [
                "up",
                "--build",
                "-d",
                "api",
                "worker",
                "redis",
                "postgres",
                "social-analyzer",
                "google-maps-scraper",
                "email-verifier",
                "reacher",
            ],
            cwd=COMPOSE_DIR,
        )

        code = ""
        for _ in range(60):
            code = curl_code(f"{BASE}/health")
            if code == "200":
                break
            time.sleep(2)
        if code != "200":
            raise SystemExit(f"API health never returned 200 (last={code})")
        print("PASS  health 200")

        run(
            COMPOSE
            + [
                "exec",
                "-T",
                "worker",
                "sh",
                "-c",
                (
                    "set -e; "
                    "python -c \"import urllib.request; urllib.request.urlopen('http://social-analyzer:9005/health')\"; "
                    "python -c \"import urllib.request; urllib.request.urlopen('http://google-maps-scraper:8080/health')\"; "
                    "python -c \"import urllib.request; urllib.request.urlopen('http://email-verifier:8080/v1/health@example.com/verification')\"; "
                    "python -c \"import urllib.request; urllib.request.urlopen('http://reacher:8080/health')\""
                ),
            ],
            cwd=COMPOSE_DIR,
        )
        print("PASS  worker can reach all fake sidecars")

        probe = SCRIPT.read_text(encoding="utf-8")
        run(
            COMPOSE
            + [
                "exec",
                "-T",
                "api",
                "sh",
                "-c",
                (
                    "set -e; export E2E_BASE_URL=http://127.0.0.1:8000; "
                    "export E2E_BACKEND_ROOT=/app/backend; "
                    "cd /app/backend; mkdir -p /app/backend/.e2e-results; python -"
                ),
            ],
            cwd=COMPOSE_DIR,
            input_text=probe,
        )
        print("PASS  fake sidecar probe")

        report = subprocess.run(
            COMPOSE
            + [
                "exec",
                "-T",
                "api",
                "cat",
                "/app/backend/.e2e-results/fake-sidecars-report.json",
            ],
            cwd=COMPOSE_DIR,
            capture_output=True,
            text=True,
            check=True,
        )
        (RESULTS / "fake-sidecars-report.json").write_text(report.stdout, encoding="utf-8")
        print("All fake sidecar E2E checks passed.")
        return 0
    finally:
        if os.environ.get("E2E_KEEP_STACK", "0") != "1":
            subprocess.run(COMPOSE + ["down"], cwd=str(COMPOSE_DIR), check=False)


if __name__ == "__main__":
    raise SystemExit(main())
