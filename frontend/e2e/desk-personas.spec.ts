import { expect, test, type Page } from "@playwright/test";

const playwrightPort = Number(process.env.PLAYWRIGHT_PORT ?? "3100");
// Cold Next compilation and persona matrices need aggregate time beyond Playwright's 30s default.
const CONTEXT_CLEANUP_ALLOWANCE_MS = 5_000;
const LOGIN_PERSONA_MATRIX_ASSERTION_BUDGET_MS = 120_000;
const OWNER_ROUTE_MATRIX_ASSERTION_BUDGET_MS = 90_000;
const DENIED_ROUTE_MATRIX_ASSERTION_BUDGET_MS = 60_000;
const COLD_NEXT_ROUTE_NAVIGATION_TIMEOUT_MS = 60_000;

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

function identity(roleName: string | null, isSuperuser = false): Identity {
  return {
    id: `qa-e2e-${roleName ?? "candidate"}`,
    email: `${roleName ?? "candidate"}@example.test`,
    first_name: "QA",
    last_name: roleName ?? "Candidate",
    is_verified: true,
    is_active: true,
    is_superuser: isSuperuser,
    role_id: roleName ? `role-${roleName}` : null,
    role_name: roleName,
    permissions: [],
    created_at: "2026-01-01T00:00:00.000Z",
    updated_at: "2026-01-01T00:00:00.000Z",
  };
}

async function mockIdentity(page: Page, user: Identity): Promise<void> {
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

async function mockLogin(page: Page, user: Identity): Promise<void> {
  let authenticated = false;
  await page.unrouteAll({ behavior: "wait" });
  await page.route("**/api/**", (route) => route.fulfill({ json: { success: true, data: {} } }));
  await page.route("**/api/auth/me", (route) =>
    authenticated
      ? route.fulfill({ json: user })
      : route.fulfill({ status: 401, json: { detail: "Unauthorized" } }),
  );
  await page.route("**/api/auth/login", async (route) => {
    authenticated = true;
    await route.fulfill({
      json: { success: true, data: { user, message: "Login successful" } },
    });
  });
}

test.describe("frozen product-door persona contract", () => {
  test("each persona lands at its approved home after login", async ({ browser }) => {
    const cases = [
      [identity(null), "/app/matches"],
      [identity("recruiter"), "/desk/sourcing-leads"],
      [identity("support"), "/desk/users"],
      [identity("admin"), "/desk"],
      [identity("team_owner"), "/desk"],
      [identity(null, true), "/desk"],
    ] as const;
    test.setTimeout(LOGIN_PERSONA_MATRIX_ASSERTION_BUDGET_MS);

    for (const [user, expectedPath] of cases) {
      const context = await browser.newContext();
      try {
        const page = await context.newPage();
        await mockLogin(page, user);
        await page.goto("/login");
        await page.getByLabel("Email").fill(user.email);
        await page.getByLabel("Password").fill("IntegrationTest123");
        await page.getByRole("button", { name: "Sign In" }).click();
        await expect(
          page,
          user.role_name ?? (user.is_superuser ? "superuser" : "candidate"),
        ).toHaveURL(new RegExp(`${expectedPath.replace(/\//g, "\\/")}$`), { timeout: 15_000 });
      } finally {
        test.info().setTimeout(test.info().timeout + CONTEXT_CLEANUP_ALLOWANCE_MS);
        await context.close();
      }
    }
  });

  test("Roles, Feature flags, and Queues allow only named owner personas", async ({ browser }) => {
    const protectedRoutes = ["/desk/roles", "/desk/feature-flags", "/desk/queues"] as const;
    const allowed = [identity("admin"), identity("team_owner"), identity(null, true)] as const;
    test.setTimeout(OWNER_ROUTE_MATRIX_ASSERTION_BUDGET_MS);

    for (const user of allowed) {
      for (const protectedRoute of protectedRoutes) {
        const context = await browser.newContext();
        try {
          const page = await context.newPage();
          await mockIdentity(page, user);
          await page.goto(protectedRoute, { waitUntil: "domcontentloaded" });
          await expect(page).toHaveURL(new RegExp(`${protectedRoute.replace(/\//g, "\\/")}$`));
        } finally {
          test.info().setTimeout(test.info().timeout + CONTEXT_CLEANUP_ALLOWANCE_MS);
          await context.close();
        }
      }
    }
  });

  test("permissions cannot elevate a non-owner into owner-only Desk routes", async ({
    browser,
  }) => {
    const forgedPermissionUser: Identity = {
      ...identity("recruiter"),
      permissions: [
        { resource: "roles", action: "read" },
        { resource: "feature_flags", action: "read" },
        { resource: "queues", action: "read" },
      ],
    };
    const protectedRoutes = ["/desk/roles", "/desk/feature-flags", "/desk/queues"] as const;
    test.setTimeout(DENIED_ROUTE_MATRIX_ASSERTION_BUDGET_MS);

    for (const protectedRoute of protectedRoutes) {
      const context = await browser.newContext();
      try {
        const page = await context.newPage();
        await mockIdentity(page, forgedPermissionUser);
        await page.goto(protectedRoute, { waitUntil: "domcontentloaded" });
        await expect(page).toHaveURL(/\/desk\/sourcing-leads$/, { timeout: 15_000 });
      } finally {
        test.info().setTimeout(test.info().timeout + CONTEXT_CLEANUP_ALLOWANCE_MS);
        await context.close();
      }
    }
  });

  test("candidate-only sessions are denied every Desk direct route", async ({ browser }) => {
    const protectedRoutes = [
      "/desk",
      "/desk/roles",
      "/desk/feature-flags",
      "/desk/queues",
    ] as const;
    test.setTimeout(DENIED_ROUTE_MATRIX_ASSERTION_BUDGET_MS);

    for (const protectedRoute of protectedRoutes) {
      const context = await browser.newContext();
      try {
        const page = await context.newPage();
        await mockIdentity(page, identity(null));
        await page.goto(protectedRoute, {
          waitUntil: "domcontentloaded",
          timeout: COLD_NEXT_ROUTE_NAVIGATION_TIMEOUT_MS,
        });
        await expect(page).toHaveURL(/\/app\/matches$/, { timeout: 15_000 });
      } finally {
        test.info().setTimeout(test.info().timeout + CONTEXT_CLEANUP_ALLOWANCE_MS);
        await context.close();
      }
    }
  });
});
