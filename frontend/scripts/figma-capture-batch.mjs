/**
 * Batch-open local URLs with Figma capture hashes.
 * Usage: node scripts/figma-capture-batch.mjs <json-array-of-{path,captureId}>
 * Or pass path=captureId pairs as args: /recruiters=uuid /candidates=uuid
 */
import { chromium } from "@playwright/test";

function buildUrl(path, captureId) {
  const endpoint = encodeURIComponent(
    `https://mcp.figma.com/mcp/capture/${captureId}/submit?bindVariables=true`,
  );
  const base = `http://localhost:3000${path}`;
  return `${base}#figmacapture=${captureId}&figmaendpoint=${endpoint}&figmadelay=3000`;
}

const pairs = process.argv.slice(2).map((arg) => {
  const eq = arg.indexOf("=");
  if (eq === -1) throw new Error(`Bad arg: ${arg}`);
  return { path: arg.slice(0, eq), captureId: arg.slice(eq + 1) };
});

if (pairs.length === 0) {
  console.error("Usage: node scripts/figma-capture-batch.mjs /path=captureId ...");
  process.exit(1);
}

const browser = await chromium.launch({ headless: true });
const results = [];

await Promise.all(
  pairs.map(async ({ path, captureId }) => {
    const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
    page.setDefaultTimeout(120_000);
    const url = buildUrl(path, captureId);
    try {
      await page.goto(url, { waitUntil: "domcontentloaded", timeout: 120_000 });
      await page.waitForTimeout(15_000);
      results.push({ path, captureId, ok: true });
      console.log("ok", path, captureId);
    } catch (err) {
      results.push({ path, captureId, ok: false, error: err?.message ?? String(err) });
      console.error("fail", path, captureId, err?.message ?? err);
    } finally {
      await page.close();
    }
  }),
);

await browser.close();
console.log(JSON.stringify(results));
const failed = results.filter((r) => !r.ok);
process.exitCode = failed.length ? 1 : 0;
