import { test, expect } from "@playwright/test";

const BACKEND_URL = (process.env.BACKEND_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

async function pollBackendHealth(maxAttempts = 60, intervalMs = 2000): Promise<void> {
  let lastError = "unknown";

  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    try {
      const response = await fetch(`${BACKEND_URL}/health`);
      if (response.status === 200) {
        return;
      }
      lastError = `HTTP ${response.status}`;
    } catch (error) {
      lastError = error instanceof Error ? error.message : String(error);
    }
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }

  throw new Error(`Backend at ${BACKEND_URL}/health did not return 200 (last: ${lastError})`);
}

test.describe.configure({ mode: "serial" });

test.beforeAll(async () => {
  await pollBackendHealth();
});

test.describe("Live backend integration", () => {
  let jobId: string;

  test("BFF health route returns success envelope", async ({ request }) => {
    const response = await request.get("/api/health");
    expect(response.ok()).toBeTruthy();
    const body = await response.json();
    expect(body.success).toBe(true);
    expect(body.data).toMatchObject({ status: expect.any(String), service: expect.any(String) });
  });

  test("health page reports live backend (not mock)", async ({ page }) => {
    await page.goto("/desk/system-health");
    await expect(page.getByRole("heading", { name: "Self-checks" })).toBeVisible();
    await expect(page.getByText("OK", { exact: true })).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("hyrepath-enrichment-mock")).toHaveCount(0);
  });

  test("sync enrich completes dossier", async ({ page }) => {
    const username = `e2e-${Date.now()}`;

    await page.goto("/osint");
    await expect(page.getByRole("heading", { name: "Look someone up" })).toBeVisible();

    await page.getByLabel("Quick (sync)").click();
    await page.getByRole("textbox", { name: /Username/ }).fill(username);

    // Tiers 2 (Username Discovery) and 3 (Deep OSINT) are checked by default
    // in sync mode; tier 1 is unavailable and tier 4 needs extra fields we
    // aren't filling here, so the defaults are exactly what this test wants.
    await expect(page.getByRole("checkbox", { name: /Username Discovery/ })).toBeChecked();
    await expect(page.getByRole("checkbox", { name: /Deep OSINT/ })).toBeChecked();

    await expect(page.getByRole("button", { name: "Look up" })).toBeEnabled({ timeout: 15_000 });
    await page.getByRole("button", { name: "Look up" }).click();

    await expect(page).toHaveURL(/\/osint\/jobs\/.+/, { timeout: 120_000 });
    await expect(page.getByRole("heading", { name: "Job dossier" })).toBeVisible();
    await expect(page.getByText("completed", { exact: true })).toBeVisible({ timeout: 60_000 });

    const match = page.url().match(/\/osint\/jobs\/([^/?#]+)/);
    expect(match?.[1]).toBeTruthy();
    jobId = match![1];
  });

  test("job detail page loads", async ({ page }) => {
    test.skip(!jobId, "requires job from sync enrich test");

    await page.goto(`/osint/jobs/${jobId}`);
    await expect(page.getByRole("heading", { name: "Job dossier" })).toBeVisible();
    await expect(page.locator("code").filter({ hasText: jobId })).toBeVisible();
  });

  test("jobs page shows at least one historical job", async ({ page }) => {
    test.skip(!jobId, "requires job from sync enrich test");

    await page.goto("/osint/jobs");
    await expect(page.getByRole("heading", { name: "Jobs" })).toBeVisible();
    await expect(page.locator("table tbody tr").first()).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText(jobId)).toBeVisible();
  });

  test("Desk owner landing reports system health without error", async ({ page }) => {
    await page.goto("/desk");
    await expect(page.getByRole("heading", { name: "Self-checks" })).toBeVisible();
    await expect(page.getByText("System health unavailable")).toHaveCount(0);
  });

  test("opt-out submission succeeds", async ({ page }) => {
    await page.goto("/opt-out");
    await expect(page.getByRole("heading", { name: /opt out of enrichment/i })).toBeVisible();
    await page.getByLabel("Identifier").fill(`e2e-optout-${Date.now()}@example.com`);
    await page.getByRole("button", { name: /submit opt out/i }).click();
    await expect(page.getByTestId("opt-out-success")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("Request accepted")).toBeVisible();
  });
});
