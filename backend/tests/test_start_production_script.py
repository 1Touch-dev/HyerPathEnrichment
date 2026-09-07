"""Regression tests for backend/scripts/start_production.sh startup selection."""

from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path


BACKEND = Path(__file__).resolve().parents[1]
SCRIPT_PATH = BACKEND / "scripts" / "start_production.sh"


def _bash_path(path: Path) -> str:
    posix = path.as_posix()
    if len(posix) >= 3 and posix[1:3] == ":/":
        return f"/{posix[0].lower()}{posix[2:]}"
    return posix


SCRIPT_PATH_BASH = _bash_path(SCRIPT_PATH)


def _wsl_path(path: Path) -> str:
    posix = path.as_posix()
    if len(posix) >= 3 and posix[1:3] == ":/":
        return f"/mnt/{posix[0].lower()}{posix[2:]}"
    return posix


def _wsl_env_value(value: str) -> str:
    posix = value.replace("\\", "/")
    if len(posix) >= 3 and posix[1:3] == ":/":
        return f"/mnt/{posix[0].lower()}{posix[2:]}"
    return value


def _write_env(tmp_path: Path, *, extra_lines: list[str] | None = None) -> Path:
    lines = [
        "API_TOKEN=test-token",
        "POSTGRES_USER=hyrepath",
        "POSTGRES_PASSWORD=test-password",
        "WORKER_QUEUE_MODE=per_tier",
    ]
    if extra_lines:
        lines.extend(extra_lines)

    env_file = tmp_path / "test.env"
    env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return env_file


def _run_script(
    env_file: Path, *args: str, env_overrides: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    for key in ("PYTEST_USE_REAL_INFRA", "TEST_DATABASE_URL", "TEST_REDIS_URL"):
        env.pop(key, None)

    if os.name == "nt":
        quoted_args = " ".join(shlex.quote(arg) for arg in args)
        exports = ""
        if env_overrides:
            exports = " ".join(
                f"{key}={shlex.quote(_wsl_env_value(value))}"
                for key, value in env_overrides.items()
            )
            exports = f"{exports} "
        command = (
            f"{exports}API_ENV_FILE={shlex.quote(_wsl_path(env_file))} "
            f"bash {shlex.quote(_wsl_path(SCRIPT_PATH))} "
            f"--skip-validation --dry-run {quoted_args}".strip()
        )
        return subprocess.run(
            ["wsl", "bash", "-lc", command],
            cwd=str(BACKEND),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

    env["API_ENV_FILE"] = str(env_file)
    if env_overrides:
        env.update(env_overrides)
    return subprocess.run(
        ["bash", SCRIPT_PATH_BASH, "--skip-validation", "--dry-run", *args],
        cwd=str(BACKEND),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_linux_mlx_dry_run_uses_tier_workers_and_removes_orphans(tmp_path: Path) -> None:
    env_file = _write_env(tmp_path)

    completed = _run_script(env_file, "--with-linux-mlx")

    assert completed.returncode == 0
    assert "tier1: on (linux-mlx)" in completed.stdout
    assert (
        "workers: supported (aux + email + cleanup + job-matching + tier1 + tier234)"
        in completed.stdout
    )
    assert "docker-compose.foundation.yml" in completed.stdout
    assert "docker-compose.tier-workers.yml" in completed.stdout
    assert "docker-compose.multilogin.yml" in completed.stdout
    assert "docker-compose.tier1.yml" not in completed.stdout
    assert "worker-email" in completed.stdout
    assert "worker-cleanup" in completed.stdout
    assert "worker-job-matching" in completed.stdout
    assert "remove orphans: yes" in completed.stdout


def test_per_tier_env_dry_run_auto_enables_tier_workers(tmp_path: Path) -> None:
    env_file = _write_env(tmp_path)

    completed = _run_script(env_file)

    assert completed.returncode == 0
    assert "workers: supported (aux + email + cleanup + job-matching + tier234)" in completed.stdout
    assert "docker-compose.foundation.yml" in completed.stdout
    assert "docker-compose.tier-workers.yml" in completed.stdout
    assert "docker-compose.multilogin.yml" not in completed.stdout
    assert "docker-compose.tier1.yml" not in completed.stdout
    assert "worker-email" in completed.stdout
    assert "worker-cleanup" in completed.stdout
    assert "worker-job-matching" in completed.stdout


def test_enable_linux_mlx_env_auto_enables_supported_linux_topology(tmp_path: Path) -> None:
    env_file = _write_env(
        tmp_path,
        extra_lines=[
            "ENABLE_LINUX_MLX=true",
        ],
    )

    completed = _run_script(env_file)

    assert completed.returncode == 0
    assert "tier1: on (linux-mlx)" in completed.stdout
    assert "docker-compose.foundation.yml" in completed.stdout
    assert "docker-compose.tier-workers.yml" in completed.stdout
    assert "docker-compose.multilogin.yml" in completed.stdout
    assert "docker-compose.tier1.yml" not in completed.stdout
    assert "worker-tier1" in completed.stdout
    assert "multilogin" in completed.stdout


def test_real_linux_tier1_without_linux_mlx_is_rejected(tmp_path: Path) -> None:
    env_file = _write_env(
        tmp_path,
        extra_lines=[
            "ENABLE_TIER1=true",
        ],
    )

    completed = _run_script(
        env_file,
        env_overrides={"START_PRODUCTION_HOST_PLATFORM": "linux"},
    )

    assert completed.returncode == 1
    assert "real Linux Tier 1 requires --with-linux-mlx" in completed.stderr
