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
  test("dashboard renders KPI cards", async ({ page }) => {
    await page.goto("/app/dashboard");
    await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
    await expect(page.getByText("Total jobs")).toBeVisible();
    await expect(page.getByText("Success rate")).toBeVisible();
  });

  test("health page reports mock backend status", async ({ page }) => {
    await page.goto("/app/health");
    await expect(page.getByRole("heading", { name: "System health" })).toBeVisible();
    await expect(page.getByText("ok", { exact: true })).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("hyrepath-enrichment-mock")).toBeVisible();
  });

  test("signals page lists mock change notifications", async ({ page }) => {
    await page.goto("/app/signals");
    await expect(page.getByRole("heading", { name: "Signals" })).toBeVisible();
    await expect(page.getByText("Acme Careers")).toBeVisible({ timeout: 15_000 });
  });
});
