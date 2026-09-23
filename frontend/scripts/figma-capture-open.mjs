/**
 * Opens a local URL with Figma capture hash in Chromium (headless-capable).
 * Usage: node scripts/figma-capture-open.mjs <url-with-hash>
 */
import { chromium } from "@playwright/test";

const url = process.argv[2];
if (!url) {
  console.error("Usage: node scripts/figma-capture-open.mjs <url>");
  process.exit(1);
}

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
page.setDefaultTimeout(120_000);

try {
  await page.goto(url, { waitUntil: "domcontentloaded", timeout: 120_000 });
  // Allow capture.js + figmadelay to run and submit
  await page.waitForTimeout(12_000);
  console.log("opened_ok", page.url());
} catch (err) {
  console.error("open_failed", err?.message ?? err);
  process.exitCode = 1;
} finally {
  await browser.close();
}
