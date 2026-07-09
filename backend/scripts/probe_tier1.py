"""Probe Tier 1 Multilogin + Selenium connectivity.

Usage:
  cd backend
  python scripts/probe_tier1.py --prereqs
  python scripts/probe_tier1.py --connect-test
  python scripts/probe_tier1.py --scrape --linkedin-url https://www.linkedin.com/in/someone

Loads `.env` from backend/ via get_settings(). Live MLX/LinkedIn calls are manual
only — not run in CI.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import get_settings
from app.providers.linkedin_browser import LinkedInBrowserClient, LinkedInPhotoError
from app.providers.multilogin import MultiloginClient, MultiloginError
from app.providers.profile_pool import ProfilePool

LINKEDIN_LOGIN_URL = "https://www.linkedin.com/login"


@dataclass
class PrereqRow:
    name: str
    present: bool
    detail: str


def audit_prerequisites() -> list[PrereqRow]:
    settings = get_settings()
    rows: list[PrereqRow] = []

    def env(name: str, value: str, env_key: str) -> None:
        ok = bool(value.strip())
        rows.append(PrereqRow(name=name, present=ok, detail=value.strip() or f"{env_key} unset"))

    env("ENABLE_TIER1", str(settings.enable_tier1).lower(), "ENABLE_TIER1")
    env("BROWSER_MODE", settings.browser_mode, "BROWSER_MODE")
    env("MULTILOGIN_EMAIL", settings.multilogin_email, "MULTILOGIN_EMAIL")
    env(
        "MULTILOGIN_PASSWORD",
        "***" if settings.multilogin_password.get_secret_value().strip() else "",
        "MULTILOGIN_PASSWORD",
    )
    env("MULTILOGIN_FOLDER_ID", settings.multilogin_folder_id, "MULTILOGIN_FOLDER_ID")
    env("MULTILOGIN_API_URL", settings.multilogin_api_url, "MULTILOGIN_API_URL")
    env("MULTILOGIN_LAUNCHER_URL", settings.multilogin_launcher_url, "MULTILOGIN_LAUNCHER_URL")
    env("MULTILOGIN_SELENIUM_HOST", settings.multilogin_selenium_host, "MULTILOGIN_SELENIUM_HOST")
    env("LINKEDIN_BOT_EMAIL", settings.linkedin_bot_email, "LINKEDIN_BOT_EMAIL")
    env(
        "LINKEDIN_BOT_PASSWORD",
        "***" if settings.linkedin_bot_password.get_secret_value().strip() else "",
        "LINKEDIN_BOT_PASSWORD",
    )

    try:
        import selenium  # noqa: F401

        rows.append(PrereqRow(name="selenium", present=True, detail="package installed"))
    except ImportError:
        rows.append(
            PrereqRow(
                name="selenium",
                present=False,
                detail="pip install selenium (worker image or pip install selenium)",
            )
        )

    return rows


def print_prereqs(rows: list[PrereqRow]) -> None:
    print("== Tier 1 prerequisites ==")
    for row in rows:
        mark = "OK" if row.present else "MISS"
        print(f"{mark:4}  {row.name}: {row.detail}")


async def connect_test(*, linkedin_url: str) -> int:
    settings = get_settings()
    mlx = MultiloginClient()
    pool = ProfilePool(mlx)
    profile_id: str | None = None
    driver = None

    try:
        token = await mlx.sign_in()
        print("Multilogin sign-in: OK")

        profile_ids = await mlx.list_profiles(token)
        if not profile_ids:
            print("No profiles found in configured folder.")
            return 1
        print(f"Profiles in folder: {len(profile_ids)}")

        profile_id = await pool.acquire()
        print(f"Acquired profile: {profile_id}")

        port = await mlx.start_profile(profile_id, token)
        print(f"Profile started on Selenium port: {port}")

        try:
            from selenium import webdriver
            from selenium.webdriver.chromium.options import ChromiumOptions
        except ImportError:
            print("selenium not installed — cannot complete browser connect test")
            return 1

        host = settings.multilogin_selenium_host.rstrip("/")
        options = ChromiumOptions()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        driver = webdriver.Remote(command_executor=f"{host}:{port}", options=options)
        driver.set_page_load_timeout(settings.tier1_browser_timeout_seconds)
        driver.get(linkedin_url)
        title = driver.title or "(no title)"
        print(f"Opened {linkedin_url}")
        print(f"Page title: {title}")
        return 0
    except MultiloginError as exc:
        print(f"Multilogin error: {exc}")
        return 1
    except Exception as exc:
        print(f"Connect test failed: {exc}")
        return 1
    finally:
        if driver is not None:
            driver.quit()
        if profile_id is not None:
            try:
                await mlx.stop_profile(profile_id)
                print(f"Stopped profile: {profile_id}")
            except MultiloginError as exc:
                print(f"Warning: stop_profile failed: {exc}")


async def scrape_test(*, linkedin_url: str) -> int:
    client = LinkedInBrowserClient()
    result = await client.scrape_photo(linkedin_url, job_id="probe")
    if result.outcome != LinkedInPhotoError.SUCCESS or not result.image_bytes:
        print(f"Scrape failed: {result.outcome}")
        return 1

    print(f"Scrape OK: {len(result.image_bytes)} bytes")
    print(f"Content-Type: {result.content_type}")
    print(f"Method: {result.method}")
    print(f"Confidence: {result.confidence}")
    return 0


async def main() -> int:
    parser = argparse.ArgumentParser(description="Probe Tier 1 Multilogin + Selenium")
    parser.add_argument(
        "--prereqs",
        action="store_true",
        help="Audit env vars and selenium package only",
    )
    parser.add_argument(
        "--connect-test",
        action="store_true",
        help="Sign in, start a profile, connect Selenium, open a page, stop profile",
    )
    parser.add_argument(
        "--scrape",
        action="store_true",
        help="Full LinkedIn photo scrape for --linkedin-url (requires MLX + bot credentials)",
    )
    parser.add_argument(
        "--linkedin-url",
        default=LINKEDIN_LOGIN_URL,
        help="Profile or login URL for --connect-test / --scrape",
    )
    args = parser.parse_args()

    rows = audit_prerequisites()
    print_prereqs(rows)

    if args.prereqs:
        return 0

    if args.connect_test:
        return await connect_test(linkedin_url=args.linkedin_url)

    if args.scrape:
        return await scrape_test(linkedin_url=args.linkedin_url)

    print("\nPass --prereqs, --connect-test, or --scrape.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
