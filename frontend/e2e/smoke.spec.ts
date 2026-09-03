import { test, expect } from "@playwright/test";

test.describe("Public surfaces", () => {
  test("hub page loads with console and opt-out CTAs", async ({ page }) => {
    await page.goto("/");
    await expect(
      page.getByRole("heading", { name: /multi-tier public-signal dossier/i }),
    ).toBeVisible();
    await expect(page.getByRole("main").getByRole("link", { name: "Open console" })).toBeVisible();
    await expect(
      page.getByRole("main").getByRole("link", { name: "Public opt-out" }),
    ).toBeVisible();
  });

  test("opt-out page accepts a mock submission", async ({ page }) => {
    await page.goto("/opt-out");
    await expect(page.getByRole("heading", { name: /opt out of enrichment/i })).toBeVisible();
    await expect(page.getByTestId("opt-out-form")).toBeVisible();
    await page.getByLabel("Identifier").fill("smoke-test@example.com");
    await page.getByRole("button", { name: /submit opt out/i }).click();
    await expect(page.getByTestId("opt-out-success")).toBeVisible();
    await expect(page.getByText("Request accepted")).toBeVisible();
  });

  test("audience landing page loads", async ({ page }) => {
    await page.goto("/recruiters");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await expect(
      page.getByRole("link", { name: /run enrichment|open console/i }).first(),
    ).toBeVisible();
  });
});

test.describe("Console shell", () => {
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

  test("OSINT lookup renders canonical intake", async ({ page }) => {
    await page.goto("/osint");
    await expect(page.getByRole("heading", { name: "Look someone up" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Open jobs" })).toBeVisible();
  });

  test("health page reports mock backend status", async ({ page }) => {
    await page.goto("/desk/system-health");
    await expect(page.getByRole("heading", { name: "Self-checks" })).toBeVisible();
    await expect(page.getByText("OK", { exact: true })).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("hyrepath-enrichment-mock")).toBeVisible();
  });

  test("signals page lists mock change notifications", async ({ page }) => {
    await page.goto("/desk/signals");
    await expect(page.getByRole("heading", { name: "Signals" })).toBeVisible();
    await expect(page.getByText("Acme Careers")).toBeVisible({ timeout: 15_000 });
  });
});
