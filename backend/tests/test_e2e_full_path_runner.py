from pathlib import Path

from scripts.e2e_full_path_runner import (
    DEFAULT_OUTREACH_PHYSICAL_ADDRESS,
    ensure_e2e_compose_defaults,
)

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def test_ensure_e2e_compose_defaults_fills_missing_address() -> None:
    env: dict[str, str] = {}
    ensure_e2e_compose_defaults(env)
    assert env["OUTREACH_PHYSICAL_ADDRESS"] == DEFAULT_OUTREACH_PHYSICAL_ADDRESS


def test_ensure_e2e_compose_defaults_preserves_explicit_address() -> None:
    env = {"OUTREACH_PHYSICAL_ADDRESS": "1 Explicit Ave"}
    ensure_e2e_compose_defaults(env)
    assert env["OUTREACH_PHYSICAL_ADDRESS"] == "1 Explicit Ave"


def test_compose_e2e_scripts_export_outreach_address() -> None:
    for name in ("e2e_compose_test.sh", "e2e_fake_sidecars.sh"):
        text = (SCRIPTS / name).read_text(encoding="utf-8")
        assert "source" in text and "_e2e_common.sh" in text
        assert "e2e_export_compose_defaults" in text
        assert "e2e_wait_for_health" in text
        assert "e2e_seed_verified_staff" in text


def test_e2e_common_helper_defaults_can_spam_address() -> None:
    text = (SCRIPTS / "_e2e_common.sh").read_text(encoding="utf-8")
    assert "OUTREACH_PHYSICAL_ADDRESS" in text
    assert DEFAULT_OUTREACH_PHYSICAL_ADDRESS in text
    assert "e2e_seed_verified_staff" in text
    assert "e2e_login_cookie_header" in text
    assert "ALLOW_E2E_SUPERUSER_BOOTSTRAP=1" in text
    assert "/auth/login" in text


def test_compose_e2e_uses_staff_cookie_not_legacy_api_token() -> None:
    compose = (SCRIPTS / "e2e_compose_test.sh").read_text(encoding="utf-8")
    assert "Authorization: Bearer" not in compose
    assert "e2e_login_cookie_header" in compose
    assert "Cookie: access_token=" in (SCRIPTS / "_e2e_common.sh").read_text(encoding="utf-8")

    fake_sh = (SCRIPTS / "e2e_fake_sidecars.sh").read_text(encoding="utf-8")
    assert "E2E_USER_EMAIL" in fake_sh
    assert "E2E_USER_PASSWORD" in fake_sh

    fake_py = (SCRIPTS / "e2e_fake_sidecars.py").read_text(encoding="utf-8")
    assert "Authorization" not in fake_py or "Bearer" not in fake_py
    assert "async def authenticate" in fake_py
    assert 'self.headers = {"Cookie": f"access_token={token}"}' in fake_py

    runner = (SCRIPTS / "e2e_fake_sidecars_runner.py").read_text(encoding="utf-8")
    assert "create_test_user.py" in runner
    assert "ALLOW_E2E_SUPERUSER_BOOTSTRAP=1" in runner
