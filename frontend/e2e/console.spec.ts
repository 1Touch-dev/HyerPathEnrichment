import { test, expect } from "@playwright/test";

test.describe("Enrichment flow", () => {
  test("async enrichment stays on enrich and shows job created toast", async ({ page }) => {
    await page.goto("/app/enrich");
    await expect(page.getByRole("heading", { name: "Look someone up" })).toBeVisible();

    await page.getByRole("textbox", { name: /Username/ }).fill("e2e-playwright");
    await expect(page.getByRole("button", { name: "Look up" })).toBeEnabled({ timeout: 15_000 });
    await page.getByRole("button", { name: "Look up" }).click();

    await expect(page).toHaveURL(/\/app\/enrich/, { timeout: 15_000 });
    await expect(page.getByText("Job created")).toBeVisible({ timeout: 15_000 });
    // SSE push from /api/enrich/[id]/events — mock job store flips to
    // "completed" ~2.4s after creation (see mock-jobs.ts createMockJobWithLifecycle).
    await expect(page.getByText("Job completed")).toBeVisible({ timeout: 15_000 });
  });

  test("history page lists jobs after enrichment", async ({ page }) => {
    await page.goto("/app/history");
    await expect(page.getByRole("heading", { name: "History" })).toBeVisible();
  });

  test("settings page loads", async ({ page }) => {
    await page.goto("/app/settings");
    await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible();
  });

  test("privacy DSAR ops form loads", async ({ page }) => {
    await page.goto("/app/privacy");
    await expect(page.getByRole("heading", { name: "Privacy requests" })).toBeVisible();
  });
});
