import { expect, test, type Page } from "@playwright/test";

const playwrightPort = Number(process.env.PLAYWRIGHT_PORT ?? "3100");

if (!Number.isInteger(playwrightPort) || playwrightPort < 1 || playwrightPort > 65_535) {
  throw new Error("PLAYWRIGHT_PORT must be an integer between 1 and 65535");
}

test.use({
  baseURL: process.env.QA_E2E_BASE_URL ?? `http://127.0.0.1:${playwrightPort}`,
});

const candidate = {
  id: "qa-e2e-responsive-candidate",
  email: "candidate@example.test",
  first_name: "QA",
  last_name: "Candidate",
  is_verified: true,
  is_active: true,
  is_superuser: false,
  role_id: null,
  role_name: null,
  permissions: [],
  created_at: "2026-01-01T00:00:00.000Z",
  updated_at: "2026-01-01T00:00:00.000Z",
};

async function openCandidateShell(page: Page, width: number): Promise<void> {
  await page.setViewportSize({ width, height: 900 });
  await page.route("**/api/**", (route) => route.fulfill({ json: { success: true, data: {} } }));
  await page.route("**/api/auth/me", (route) => route.fulfill({ json: candidate }));
  await page.route("**/api/admin/impersonation/status", (route) =>
    route.fulfill({
      json: {
        success: true,
        data: {
          isImpersonating: false,
          targetUserId: null,
          adminEmail: null,
          expiresAt: null,
        },
      },
    }),
  );
  await page.route("**/api/enrich/jobs**", (route) =>
    route.fulfill({ json: { success: true, data: { jobs: [], total: 0 } } }),
  );
  await page.goto("/app/dashboard");
  await expect(
    page.locator("header").getByText("Candidate", { exact: true }).first(),
  ).toBeVisible();
}

async function expectNoHorizontalOverflow(page: Page): Promise<void> {
  const dimensions = await page.evaluate(() => ({
    viewport: document.documentElement.clientWidth,
    content: document.documentElement.scrollWidth,
  }));
  expect(dimensions.content).toBeLessThanOrEqual(dimensions.viewport);
}

test.describe("frozen responsive breakpoints", () => {
  test("390px uses reachable bottom navigation without clipping", async ({ page }) => {
    await openCandidateShell(page, 390);

    await expect(page.locator("aside:visible")).toHaveCount(0);
    const bottomNav = page.locator("main + nav");
    await expect(bottomNav).toBeVisible();
    await expect(bottomNav.getByRole("link", { name: "My CV" })).toBeVisible();
    await expect(bottomNav.getByRole("link", { name: "Matches" })).toBeVisible();
    await expect(bottomNav.getByRole("link", { name: "Applications" })).toBeVisible();
    const more = bottomNav.getByRole("button", { name: "More" });
    await expect(more).toBeVisible();
    expect((await more.boundingBox())?.height).toBeGreaterThanOrEqual(44);
    await expectNoHorizontalOverflow(page);
  });

  test("834px uses the compact rail and removes mobile navigation", async ({ page }) => {
    await openCandidateShell(page, 834);

    await expect(page.locator("main + nav")).toBeHidden();
    const compactRail = page.locator('aside:has(a[title="Matches"])');
    await expect(compactRail).toBeVisible();
    await expect(compactRail.locator('a[title="Matches"]')).toBeVisible();
    await expect(page.getByRole("button", { name: /sidebar/i })).toBeHidden();
    await expectNoHorizontalOverflow(page);
  });

  test("1440px uses the full sidebar with visible navigation labels", async ({ page }) => {
    await openCandidateShell(page, 1440);

    await expect(page.locator("main + nav")).toBeHidden();
    const fullSidebar = page.locator('aside:has(button[aria-label="Collapse sidebar"])');
    await expect(fullSidebar).toBeVisible();
    await expect(fullSidebar.getByRole("link", { name: "Matches" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Collapse sidebar" })).toBeVisible();
    await expectNoHorizontalOverflow(page);
  });
});
