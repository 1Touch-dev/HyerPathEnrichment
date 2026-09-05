import { test, expect } from "@playwright/test";

test.describe("Enrichment flow", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("**/api/auth/me", async (route) => {
      await route.fulfill({
        json: {
          id: "mock-staff-1",
          email: "mock.staff@hyrepath.dev",
          first_name: "Mock",
          last_name: "Staff",
          is_verified: true,
          is_active: true,
          is_superuser: true,
          role_id: null,
          role_name: null,
          permissions: [],
          created_at: "2026-01-01T00:00:00.000Z",
          updated_at: "2026-01-01T00:00:00.000Z",
        },
      });
    });
  });

  test("async enrichment stays on OSINT and shows job created toast", async ({ page }) => {
    await page.goto("/osint");
    await expect(page.getByRole("heading", { name: "Look someone up" })).toBeVisible();

    await page.getByRole("textbox", { name: /Username/ }).fill("e2e-playwright");
    await expect(page.getByRole("button", { name: "Look up" })).toBeEnabled({ timeout: 15_000 });
    await page.getByRole("button", { name: "Look up" }).click();

    await expect(page).toHaveURL(/\/osint/, { timeout: 15_000 });
    await expect(page.getByText("Job created")).toBeVisible({ timeout: 15_000 });
    // SSE push from /api/enrich/[id]/events — mock job store flips to
    // "completed" ~2.4s after creation (see mock-jobs.ts createMockJobWithLifecycle).
    await expect(page.getByText("Job completed")).toBeVisible({ timeout: 15_000 });
  });

  test("jobs page exposes queue and history", async ({ page }) => {
    await page.goto("/osint/jobs");
    await expect(page.getByRole("heading", { name: "Jobs" })).toBeVisible();
  });

  test("settings page loads", async ({ page }) => {
    await page.goto("/osint/settings");
    await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible();
  });

  test("privacy DSAR ops form loads", async ({ page }) => {
    await page.goto("/app/privacy");
    await expect(page.getByRole("heading", { name: "Privacy requests" })).toBeVisible();
  });
});
