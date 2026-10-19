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


def test_e2e_common_helper_defaults_can_spam_address() -> None:
    text = (SCRIPTS / "_e2e_common.sh").read_text(encoding="utf-8")
    assert "OUTREACH_PHYSICAL_ADDRESS" in text
    assert DEFAULT_OUTREACH_PHYSICAL_ADDRESS in text
