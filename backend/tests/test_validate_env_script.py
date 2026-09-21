"""Regression tests for env templates and validate_env.sh."""

from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
VALIDATE_SCRIPT = BACKEND / "scripts" / "validate_env.sh"
PRODUCTION_ENV = BACKEND / ".env.production.example"
STAGING_ENV = BACKEND / ".env.staging.example"


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


def _parse_env_keys(path: Path) -> set[str]:
    keys: set[str] = set()
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _ = line.split("=", 1)
        keys.add(key)
    return keys


def _run_validate(
    env_file: Path, *, env_overrides: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    for key in ("PYTEST_USE_REAL_INFRA", "TEST_DATABASE_URL", "TEST_REDIS_URL"):
        env.pop(key, None)
    if env_overrides:
        env.update(env_overrides)

    if os.name == "nt":
        exports = ""
        if env_overrides:
            exports = " ".join(
                f"{key}={shlex.quote(_wsl_env_value(value))}"
                for key, value in env_overrides.items()
            )
            exports = f"{exports} "
        command = (
            f"{exports}bash {shlex.quote(_wsl_path(VALIDATE_SCRIPT))} "
            f"{shlex.quote(_wsl_path(env_file))}"
        )
        return subprocess.run(
            ["wsl", "bash", "-lc", command],
            cwd=str(BACKEND),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )

    return subprocess.run(
        ["bash", str(VALIDATE_SCRIPT), str(env_file)],
        cwd=str(BACKEND),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def test_env_examples_include_supported_startup_keys() -> None:
    required_keys = {
        "API_TOKEN",
        "DATABASE_URL",
        "REDIS_URL",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_DB",
        "BROWSER_MODE",
        "WORKER_QUEUE_MODE",
        "ENABLE_TIER1",
        "ENABLE_LINUX_MLX",
        "OUTREACH_ENABLED",
        "OUTREACH_PHYSICAL_ADDRESS",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_DEFAULT_REGION",
    }

    assert required_keys.issubset(_parse_env_keys(PRODUCTION_ENV))
    assert required_keys.issubset(_parse_env_keys(STAGING_ENV))


def test_env_examples_keep_same_key_set() -> None:
    assert _parse_env_keys(PRODUCTION_ENV) == _parse_env_keys(STAGING_ENV)


def test_validate_env_rejects_replace_placeholders(tmp_path: Path) -> None:
    env_file = tmp_path / "placeholder.env"
    env_file.write_text(
        "\n".join(
            [
                "API_TOKEN=REPLACE_WITH_TOKEN",
                "DATABASE_URL=postgresql+asyncpg://hyrepath:REPLACE_PG_PASSWORD@postgres:5432/hyrepath",
                "REDIS_URL=redis://redis:6379/0",
                "POSTGRES_USER=hyrepath",
                "POSTGRES_PASSWORD=REPLACE_PG_PASSWORD",
                "POSTGRES_DB=hyrepath",
                "WORKER_QUEUE_MODE=per_tier",
                "OUTREACH_ENABLED=true",
                "OUTREACH_PHYSICAL_ADDRESS=REPLACE_WITH_REAL_POSTAL_ADDRESS",
                "EMAIL_VERIFIER_URL=http://email-verifier:8080",
                "SOCIAL_ANALYZER_URL=http://social-analyzer:9005",
                "GMAPS_SCRAPER_URL=http://google-maps-scraper:8080",
                "ENABLE_TIER1=false",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    completed = _run_validate(env_file)

    assert completed.returncode == 1
    assert "contains placeholder value" in completed.stdout + completed.stderr


def test_validate_env_accepts_supported_minimum_shape(tmp_path: Path) -> None:
    env_file = tmp_path / "valid.env"
    env_file.write_text(
        "\n".join(
            [
                "API_TOKEN=abcdefghijklmnopqrstuvwxyz123456",
                "DATABASE_URL=postgresql+asyncpg://hyrepath:super-secret-password@postgres:5432/hyrepath",
                "REDIS_URL=redis://redis:6379/0",
                "POSTGRES_USER=hyrepath",
                "POSTGRES_PASSWORD=super-secret-password",
                "POSTGRES_DB=hyrepath",
                "WORKER_QUEUE_MODE=per_tier",
                "OUTREACH_ENABLED=true",
                "OUTREACH_PHYSICAL_ADDRESS=123 Test St, Suite 100, Test City, TS 12345",
                "EMAIL_VERIFIER_URL=http://email-verifier:8080",
                "SOCIAL_ANALYZER_URL=http://social-analyzer:9005",
                "GMAPS_SCRAPER_URL=http://google-maps-scraper:8080",
                "ENABLE_TIER1=false",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    completed = _run_validate(env_file)

    assert completed.returncode == 0
    assert "Validation passed" in completed.stdout


def test_validate_env_rejects_linux_mlx_worker_contract_mismatch(tmp_path: Path) -> None:
    api_env = tmp_path / "api.env"
    worker_env = tmp_path / "worker.env"

    api_env.write_text(
        "\n".join(
            [
                "API_TOKEN=abcdefghijklmnopqrstuvwxyz123456",
                "DATABASE_URL=postgresql+asyncpg://hyrepath:super-secret-password@postgres:5432/hyrepath",
                "REDIS_URL=redis://redis:6379/0",
                "POSTGRES_USER=hyrepath",
                "POSTGRES_PASSWORD=super-secret-password",
                "POSTGRES_DB=hyrepath",
                "WORKER_QUEUE_MODE=per_tier",
                "OUTREACH_ENABLED=true",
                "OUTREACH_PHYSICAL_ADDRESS=123 Test St, Suite 100, Test City, TS 12345",
                "EMAIL_VERIFIER_URL=http://email-verifier:8080",
                "SOCIAL_ANALYZER_URL=http://social-analyzer:9005",
                "GMAPS_SCRAPER_URL=http://google-maps-scraper:8080",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    worker_env.write_text(
        "\n".join(
            [
                "MULTILOGIN_EMAIL=bot@example.com",
                "MULTILOGIN_PASSWORD=secret-password",
                "MULTILOGIN_FOLDER_ID=folder-123",
                "LINKEDIN_BOT_EMAIL=linkedin-bot@example.com",
                "LINKEDIN_BOT_PASSWORD=linkedin-secret",
                "BROWSER_MODE=local",
                "R2_ACCOUNT_ID=r2-account",
                "R2_ACCESS_KEY_ID=r2-access",
                "R2_SECRET_ACCESS_KEY=r2-secret",
                "R2_BUCKET=hyrepath-assets",
                "R2_PUBLIC_BASE_URL=https://cdn.example.com",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    completed = _run_validate(
        api_env,
        env_overrides={
            "VALIDATE_WORKER_ENV_FILE": str(worker_env),
            "VALIDATE_EFFECTIVE_TIER1": "true",
            "VALIDATE_EFFECTIVE_LINUX_MLX": "true",
        },
    )

    assert completed.returncode == 1
    output = completed.stdout + completed.stderr
    assert "BROWSER_MODE must be 'multilogin'" in output
    assert "AWS access key ID" in output


def test_validate_env_accepts_linux_mlx_worker_contract(tmp_path: Path) -> None:
    api_env = tmp_path / "api.env"
    worker_env = tmp_path / "worker.env"

    api_env.write_text(
        "\n".join(
            [
                "API_TOKEN=abcdefghijklmnopqrstuvwxyz123456",
                "DATABASE_URL=postgresql+asyncpg://hyrepath:super-secret-password@postgres:5432/hyrepath",
                "REDIS_URL=redis://redis:6379/0",
                "POSTGRES_USER=hyrepath",
                "POSTGRES_PASSWORD=super-secret-password",
                "POSTGRES_DB=hyrepath",
                "WORKER_QUEUE_MODE=per_tier",
                "OUTREACH_ENABLED=true",
                "OUTREACH_PHYSICAL_ADDRESS=123 Test St, Suite 100, Test City, TS 12345",
                "EMAIL_VERIFIER_URL=http://email-verifier:8080",
                "SOCIAL_ANALYZER_URL=http://social-analyzer:9005",
                "GMAPS_SCRAPER_URL=http://google-maps-scraper:8080",
                "AWS_ACCESS_KEY_ID=aws-access",
                "AWS_SECRET_ACCESS_KEY=aws-secret",
                "AWS_DEFAULT_REGION=us-east-1",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    worker_env.write_text(
        "\n".join(
            [
                "MULTILOGIN_EMAIL=bot@example.com",
                "MULTILOGIN_PASSWORD=secret-password",
                "MULTILOGIN_FOLDER_ID=folder-123",
                "LINKEDIN_BOT_EMAIL=linkedin-bot@example.com",
                "LINKEDIN_BOT_PASSWORD=linkedin-secret",
                "BROWSER_MODE=multilogin",
                "R2_ACCOUNT_ID=r2-account",
                "R2_ACCESS_KEY_ID=r2-access",
                "R2_SECRET_ACCESS_KEY=r2-secret",
                "R2_BUCKET=hyrepath-assets",
                "R2_PUBLIC_BASE_URL=https://cdn.example.com",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    completed = _run_validate(
        api_env,
        env_overrides={
            "VALIDATE_WORKER_ENV_FILE": str(worker_env),
            "VALIDATE_EFFECTIVE_TIER1": "true",
            "VALIDATE_EFFECTIVE_LINUX_MLX": "true",
        },
    )

    assert completed.returncode == 0
    assert "Linux containerized Multilogin target detected" in completed.stdout


def test_validate_env_rejects_real_linux_tier1_without_linux_mlx(tmp_path: Path) -> None:
    api_env = tmp_path / "api.env"
    worker_env = tmp_path / "worker.env"

    api_env.write_text(
        "\n".join(
            [
                "API_TOKEN=abcdefghijklmnopqrstuvwxyz123456",
                "DATABASE_URL=postgresql+asyncpg://hyrepath:super-secret-password@postgres:5432/hyrepath",
                "REDIS_URL=redis://redis:6379/0",
                "POSTGRES_USER=hyrepath",
                "POSTGRES_PASSWORD=super-secret-password",
                "POSTGRES_DB=hyrepath",
                "WORKER_QUEUE_MODE=per_tier",
                "OUTREACH_ENABLED=true",
                "OUTREACH_PHYSICAL_ADDRESS=123 Test St, Suite 100, Test City, TS 12345",
                "EMAIL_VERIFIER_URL=http://email-verifier:8080",
                "SOCIAL_ANALYZER_URL=http://social-analyzer:9005",
                "GMAPS_SCRAPER_URL=http://google-maps-scraper:8080",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    worker_env.write_text(
        "\n".join(
            [
                "MULTILOGIN_EMAIL=bot@example.com",
                "MULTILOGIN_PASSWORD=secret-password",
                "MULTILOGIN_FOLDER_ID=folder-123",
                "LINKEDIN_BOT_EMAIL=linkedin-bot@example.com",
                "LINKEDIN_BOT_PASSWORD=linkedin-secret",
                "BROWSER_MODE=multilogin",
                "R2_ACCOUNT_ID=r2-account",
                "R2_ACCESS_KEY_ID=r2-access",
                "R2_SECRET_ACCESS_KEY=r2-secret",
                "R2_BUCKET=hyrepath-assets",
                "R2_PUBLIC_BASE_URL=https://cdn.example.com",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    completed = _run_validate(
        api_env,
        env_overrides={
            "VALIDATE_WORKER_ENV_FILE": str(worker_env),
            "VALIDATE_EFFECTIVE_TIER1": "true",
            "VALIDATE_EFFECTIVE_LINUX_MLX": "false",
            "VALIDATE_HOST_PLATFORM": "linux",
        },
    )

    assert completed.returncode == 1
    assert "Effective Tier 1 on real Linux requires ENABLE_LINUX_MLX=true" in (
        completed.stdout + completed.stderr
    )
