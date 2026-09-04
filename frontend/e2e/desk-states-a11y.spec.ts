import { expect, test, type Page } from "@playwright/test";

const playwrightPort = Number(process.env.PLAYWRIGHT_PORT ?? "3100");
// A fresh Next server may compile the feature-flags route beyond Playwright's 30s default.
const COLD_NEXT_FEATURE_FLAG_ROUTE_TEST_TIMEOUT_MS = 60_000;

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
  id: "qa-e2e-candidate",
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
  id: "qa-e2e-owner",
  email: "owner@example.test",
  last_name: "Owner",
  role_id: "role-team-owner",
  role_name: "team_owner",
  permissions: [{ resource: "feature_flags", action: "read" }],
};

async function mockIdentity(page: Page, user: Identity = candidate): Promise<void> {
  await page.unrouteAll({ behavior: "wait" });
  await page.route("**/api/**", (route) => route.fulfill({ json: { success: true, data: {} } }));
  await page.route("**/api/auth/me", (route) => route.fulfill({ json: user }));
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
}

test.describe("approved Desk states and keyboard semantics", () => {
  test("login redirect preserves the complete direct-route query", async ({ page }) => {
    await page.route("**/api/**", (route) => route.fulfill({ json: { success: true, data: {} } }));
    await page.route("**/api/auth/me", (route) =>
      route.fulfill({ status: 401, json: { detail: "Unauthorized" } }),
    );

    await page.goto("/desk/queues?queue=default&state=failed");
    await expect(page).toHaveURL((url) => {
      if (url.pathname !== "/login") return false;
      return url.searchParams.get("redirect") === "/desk/queues?queue=default&state=failed";
    });

    const email = page.getByLabel("Email");
    const password = page.getByLabel("Password");
    await email.focus();
    await expect(email).toBeFocused();
    await page.keyboard.press("Tab");
    await expect(password).toBeFocused();
    await page.keyboard.press("Tab");
    await expect(page.getByRole("button", { name: "Sign In" })).toBeFocused();
  });

  test("mobile More menu traps focus, closes with Escape, and restores its trigger", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await mockIdentity(page);
    await page.goto("/app/dashboard");

    const trigger = page.getByRole("button", { name: "More" });
    await trigger.focus();
    await page.keyboard.press("Enter");
    const dialog = page.getByRole("dialog", { name: "More" });
    await expect(dialog).toBeVisible();
    await expect(dialog.getByRole("button", { name: "Close" })).toBeFocused();
    await page.keyboard.press("Escape");
    await expect(dialog).toBeHidden();
    await expect(trigger).toBeFocused();
  });

  test("route-loading state is announced without moving keyboard focus", async ({ page }) => {
    let releaseIdentity!: () => void;
    const identityReleased = new Promise<void>((resolve) => {
      releaseIdentity = resolve;
    });
    await page.route("**/api/**", (route) => route.fulfill({ json: { success: true, data: {} } }));
    await page.route("**/api/auth/me", async (route) => {
      await identityReleased;
      await route.fulfill({ json: candidate });
    });

    const navigation = page.goto("/app/dashboard");
    await expect(page.getByRole("status", { name: /loading/i })).toBeVisible();
    releaseIdentity();
    await navigation;
    await expect(page.getByRole("status", { name: /loading/i })).toBeHidden();
  });

  test("feature flags expose the frozen disabled state without mutation controls", async ({
    page,
  }) => {
    await mockIdentity(page, owner);
    await page.route("**/api/admin/feature-flags", (route) =>
      route.fulfill({
        json: {
          success: true,
          data: [
            {
              key: "candidate_ranker",
              enabled: false,
              description: "Future ranker consumer",
              updated_by: null,
              updated_at: "2026-01-01T00:00:00.000Z",
            },
          ],
        },
      }),
    );

    await page.goto("/desk/feature-flags");
    await expect(page.getByRole("heading", { name: "Feature flags" })).toBeVisible();
    await expect(page.getByText(/mutation is disabled until a consumer exists/i)).toBeVisible();
    await expect(page.getByRole("button", { name: "Create flag" })).toBeDisabled();
    await expect(page.getByRole("switch", { name: "Toggle candidate_ranker" })).toBeDisabled();
  });

  test("feature flag loading is announced as polite status", async ({ page }) => {
    await mockIdentity(page, owner);
    await page.route("**/api/admin/feature-flags", () => new Promise(() => {}));

    await page.goto("/desk/feature-flags");
    await expect(
      page.getByRole("status").filter({ hasText: /loading feature flag records/i }),
    ).toBeVisible();
  });

  test("feature flag load failure is announced as an alert", async ({ page }) => {
    test.setTimeout(COLD_NEXT_FEATURE_FLAG_ROUTE_TEST_TIMEOUT_MS);
    await mockIdentity(page, owner);
    await page.route("**/api/admin/feature-flags", (route) =>
      route.fulfill({
        status: 503,
        json: {
          success: false,
          error: {
            code: "FEATURE_FLAGS_UNAVAILABLE",
            message: "Feature flag records unavailable.",
            status_code: 503,
          },
        },
      }),
    );

    await page.goto("/desk/feature-flags");
    await expect(
      page.getByRole("alert", { name: "Feature flag records unavailable" }),
    ).toBeVisible();
  });

  test("feature flag empty state is announced as polite status", async ({ page }) => {
    await mockIdentity(page, owner);
    await page.route("**/api/admin/feature-flags", (route) =>
      route.fulfill({ json: { success: true, data: [] } }),
    );

    await page.goto("/desk/feature-flags");
    await expect(
      page.getByRole("status", { name: "No stored feature flag records" }),
    ).toBeVisible();
  });
});
