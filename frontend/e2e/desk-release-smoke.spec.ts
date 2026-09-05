import { expect, test, type Page } from "@playwright/test";

const playwrightPort = Number(process.env.PLAYWRIGHT_PORT ?? "3100");
// Candidate route compilation is bounded separately from per-assertion waits and context cleanup.
const CONTEXT_CLEANUP_ALLOWANCE_MS = 5_000;
const CANDIDATE_ROUTE_MATRIX_ASSERTION_BUDGET_MS = 90_000;
const CANDIDATE_IMPERSONATION_ASSERTION_BUDGET_MS = 90_000;
const COLD_NEXT_ROUTE_NAVIGATION_TIMEOUT_MS = 60_000;
const COLD_NEXT_ACCOUNT_LOADING_TIMEOUT_MS = 60_000;

if (!Number.isInteger(playwrightPort) || playwrightPort < 1 || playwrightPort > 65_535) {
  throw new Error("PLAYWRIGHT_PORT must be an integer between 1 and 65535");
}

test.use({
  baseURL: process.env.QA_E2E_BASE_URL ?? `http://127.0.0.1:${playwrightPort}`,
});

type Identity = {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  is_verified: boolean;
  is_active: boolean;
  is_superuser: boolean;
  role_id: string | null;
  role_name: string | null;
  permissions: { resource: string; action: string }[];
  created_at: string;
  updated_at: string;
};

const candidate: Identity = {
  id: "qa-release-candidate",
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

const owner: Identity = {
  ...candidate,
  id: "qa-release-owner",
  email: "owner@example.test",
  last_name: "Owner",
  role_id: "role-team-owner",
  role_name: "team_owner",
};

async function mockSession(page: Page, user: Identity, impersonating = false): Promise<void> {
  await page.unrouteAll({ behavior: "wait" });
  await page.route("**/api/**", (route) => route.fulfill({ json: { success: true, data: {} } }));
  await page.route("**/api/auth/me", (route) => route.fulfill({ json: user }));
  await page.route("**/api/admin/impersonation/status", (route) =>
    route.fulfill({
      json: {
        success: true,
        data: {
          isImpersonating: impersonating,
          targetUserId: impersonating ? candidate.id : null,
          adminEmail: impersonating ? "real.admin@example.test" : null,
          expiresAt: impersonating ? "2026-01-01T01:00:00.000Z" : null,
        },
      },
    }),
  );
  await page.route("**/api/enrich/jobs**", (route) =>
    route.fulfill({ json: { success: true, data: { jobs: [], total: 0 } } }),
  );
  await page.route("**/api/health", (route) =>
    route.fulfill({ json: { status: "ok", service: "qa-release-mock" } }),
  );
}

test.describe("Desk Wave 1 release smoke", () => {
  test("feature-flag mutation returns the stable read-only error", async ({ request }) => {
    const response = await request.put("/api/admin/feature-flags/candidate_ranker", {
      data: { enabled: true },
    });

    expect(response.status()).toBe(405);
    await expect(response.json()).resolves.toMatchObject({
      success: false,
      error: {
        code: "FEATURE_FLAGS_READ_ONLY",
        message: "Feature flag mutation is disabled until an application consumer exists.",
        status_code: 405,
      },
    });
  });

  test("Candidate compatibility routes remain direct pages and preserve queries", async ({
    browser,
  }) => {
    const routes = [
      ["/app/jobs?state=queued", "/app/jobs", "state=queued"],
      ["/app/history?cursor=next", "/app/history", "cursor=next"],
      ["/app/dashboard?range=7d", "/app/dashboard", "range=7d"],
      ["/app/health?probe=bff", "/app/health", "probe=bff"],
    ] as const;
    test.setTimeout(CANDIDATE_ROUTE_MATRIX_ASSERTION_BUDGET_MS);

    for (const [source, pathname, search] of routes) {
      const context = await browser.newContext();
      try {
        const page = await context.newPage();
        await mockSession(page, candidate);
        const response = await page.goto(source, {
          waitUntil: "domcontentloaded",
          timeout: COLD_NEXT_ROUTE_NAVIGATION_TIMEOUT_MS,
        });

        expect(response?.status(), source).toBeLessThan(400);
        const currentUrl = new URL(page.url());
        expect(currentUrl.pathname).toBe(pathname);
        expect(currentUrl.search).toBe(`?${search}`);
        await expect(page.getByRole("status", { name: "Loading account" })).toBeHidden({
          timeout: COLD_NEXT_ACCOUNT_LOADING_TIMEOUT_MS,
        });
        await expect(
          page.locator("header").getByText("Candidate", { exact: true }).first(),
        ).toBeVisible();
        await expect(page.getByText(/404|not found/i)).toHaveCount(0);
      } finally {
        test.info().setTimeout(test.info().timeout + CONTEXT_CLEANUP_ALLOWANCE_MS);
        await context.close();
      }
    }
  });

  test("candidate impersonation is visibly attributed and cannot cross product doors", async ({
    page,
  }) => {
    test.setTimeout(CANDIDATE_IMPERSONATION_ASSERTION_BUDGET_MS);
    await mockSession(page, candidate, true);
    await page.goto("/app/dashboard", { timeout: COLD_NEXT_ROUTE_NAVIGATION_TIMEOUT_MS });

    await expect(page.getByRole("status", { name: "Loading account" })).toBeHidden({
      timeout: COLD_NEXT_ACCOUNT_LOADING_TIMEOUT_MS,
    });
    await expect(page.getByText(new RegExp(`You are viewing as ${candidate.id}`))).toBeVisible();
    await expect(page.getByText("admin: real.admin@example.test")).toBeVisible();
    await expect(
      page.locator("header").getByText("Candidate", { exact: true }).first(),
    ).toBeVisible();
    await expect(page.getByRole("link", { name: "New enrichment" })).toHaveCount(0);
    await expect(page.getByRole("link", { name: "System health" })).toHaveCount(0);

    await page.goto("/desk/roles", {
      waitUntil: "domcontentloaded",
      timeout: COLD_NEXT_ROUTE_NAVIGATION_TIMEOUT_MS,
    });
    await expect(page).toHaveURL(/\/app\/matches$/);
  });

  test("owner can inspect feature flags but cannot mutate them", async ({ page }) => {
    await mockSession(page, owner);
    await page.route("**/api/admin/feature-flags", (route) =>
      route.fulfill({
        json: {
          success: true,
          data: [
            {
              key: "candidate_ranker",
              enabled: false,
              description: "No consumer exists",
              updated_by: null,
              updated_at: "2026-01-01T00:00:00.000Z",
            },
          ],
        },
      }),
    );

    await page.goto("/desk/feature-flags");
    await expect(page.getByRole("heading", { name: "Feature flags" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Create flag" })).toBeDisabled();
    await expect(page.getByRole("switch", { name: "Toggle candidate_ranker" })).toBeDisabled();
  });
});
