"""One-off: local Chrome Selenium proof (no Multilogin)."""
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from app.integrations.linkedin.browser_facade import (
    LinkedInPhotoError,
    _scrape_on_driver,
    download_image,
)

PROFILE_URL = "https://www.linkedin.com/in/narendramodi/?isSelfProfile=false"  # change me


def main() -> int:
    options = Options()
    # Do NOT use headless — you want to see login + captcha if it happens
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])

    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(45)

    try:
        print(f"Scraping {PROFILE_URL}...")
        partial, image_url = _scrape_on_driver(driver, PROFILE_URL)
        print(f"Scrape outcome: {partial.outcome}, method: {partial.method}, confidence: {partial.confidence}")

        if partial.outcome != LinkedInPhotoError.SUCCESS or not image_url:
            return 1

        image_bytes, content_type = asyncio.run(download_image(image_url))
        if not image_bytes:
            print("Download failed")
            return 1

        out = ROOT / "artifacts" / "tier1" / "local_proof.jpg"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(image_bytes)
        print(f"OK: {len(image_bytes)} bytes, {content_type}, saved to {out}")
        return 0
    finally:
        input("Press Enter to close the browser...")  # lets you inspect the page
        driver.quit()


if __name__ == "__main__":
    raise SystemExit(main())