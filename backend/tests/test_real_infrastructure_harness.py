"""Regression tests for the real-infrastructure proof harness scripts."""

from __future__ import annotations

from pathlib import Path


BACKEND = Path(__file__).resolve().parents[1]
SHELL_HARNESS = BACKEND / "docker" / "run_real_infrastructure_tests.sh"
POWERSHELL_HARNESS = BACKEND / "docker" / "run_real_infrastructure_tests.ps1"


def test_shell_harness_uses_compose_services_and_pytest_plugin_contract() -> None:
    content = SHELL_HARNESS.read_text(encoding="utf-8")

    assert "compose_exec api env \\" in content
    assert "-p tests.conftest_real_infrastructure" in content
    assert "PYTEST_USE_REAL_INFRA=true" in content
    assert 'TEST_DATABASE_URL="${TEST_DATABASE_URL:-postgresql+asyncpg://' in content
    assert "docker exec hyer-" not in content
    assert "docker logs hyer-" not in content
    assert "/api/admin/costs" not in content


def test_powershell_harness_delegates_to_shell_harness() -> None:
    content = POWERSHELL_HARNESS.read_text(encoding="utf-8")

    assert "bash ./run_real_infrastructure_tests.sh" in content
    assert "export REAL_INFRA_ENV_FILE=" in content
    assert "docker exec hyer-" not in content
    assert (
        "DATABASE_URL=postgresql+asyncpg://hyrepath:password@postgres:5432/hyrepath" not in content
    )
