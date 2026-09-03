import { execFileSync } from "node:child_process";
import { expect, test, type Page } from "@playwright/test";

const CANDIDATE_EMAIL = "e2e-t4-candidate@example.com";
const CANDIDATE_PASSWORD = "IntegrationCandidate123";

const deskRoutes = [
  "/desk",
  "/desk/ai-actions",
  "/desk/analytics",
  "/desk/audit-logs",
  "/desk/brands",
  "/desk/demand-intelligence",
  "/desk/documents",
  "/desk/feature-flags",
  "/desk/job-postings",
  "/desk/linkedin-tasks",
  "/desk/outreach",
  "/desk/portfolio",
  "/desk/queues",
  "/desk/review-queue",
  "/desk/roles",
  "/desk/signals",
  "/desk/sourcing-leads",
  "/desk/staff-invites",
  "/desk/system-health",
  "/desk/users",
] as const;

const redirects = [
  ["/app/enrich?tiers=tier1", "/osint?tiers=tier1"],
  ["/app/history?cursor=next", "/osint/jobs?cursor=next"],
  ["/app/jobs?state=queued", "/osint/jobs?state=queued"],
  ["/app/jobs/dossier-123?tiers=tier2&view=raw", "/osint/jobs/dossier-123?tiers=tier2&view=raw"],
  ["/app/signals?source=webhook", "/desk/signals?source=webhook"],
  ["/app/dashboard?tab=lookup", "/osint?tab=lookup"],
  ["/app/health?probe=redis", "/desk/system-health?probe=redis"],
  ["/app/admin?from=legacy", "/desk?from=legacy"],
  ["/app/admin/users/user-123?tab=audit", "/desk/users/user-123?tab=audit"],
] as const;

type DoorUser = {
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
};

function user(roleName: string | null, isSuperuser = false): DoorUser {
  return {
    id: `t4-${roleName ?? "candidate"}`,
    email: `${roleName ?? "candidate"}@example.com`,
    first_name: "T4",
    last_name: roleName ?? "Candidate",
    is_verified: true,
    is_active: true,
    is_superuser: isSuperuser,
    role_id: roleName ? `role-${roleName}` : null,
    role_name: roleName,
    permissions: [],
    created_at: "2026-01-01T00:00:00.000Z",
  };
}

async function mockIdentity(page: Page, identity: DoorUser): Promise<void> {
  await page.route("**/api/auth/me", (route) => route.fulfill({ json: identity }));
}

function unwrap<T>(body: { data?: T } | T): T {
  return body && typeof body === "object" && "data" in body ? (body.data as T) : (body as T);
}

test.describe.configure({ mode: "serial" });
test.setTimeout(180_000);

test.beforeAll(() => {
  execFileSync(
    "python3",
    [
      "scripts/create_test_user.py",
      "--email",
      CANDIDATE_EMAIL,
      "--password",
      CANDIDATE_PASSWORD,
      "--first-name",
      "T4",
      "--last-name",
      "Candidate",
    ],
    { cwd: "../backend", stdio: ["ignore", "pipe", "inherit"] },
  );
});

test("all nine compatibility redirects preserve IDs and queries", async ({ request }) => {
  for (const [source, target] of redirects) {
    const response = await request.get(source, { maxRedirects: 0 });
    expect(response.status(), source).toBe(307);
    expect(new URL(response.headers().location, "http://127.0.0.1:3000").href, source).toBe(
      new URL(target, "http://127.0.0.1:3000").href,
    );
  }
});

test("role homes and direct-route guards choose the correct door", async ({ browser }) => {
  const cases = [
    [user(null), "/osint", /\/app\/matches$/],
    [user("recruiter"), "/desk", /\/desk\/sourcing-leads$/],
    [user("support"), "/desk", /\/desk\/users$/],
    [user("admin"), "/desk", /\/desk$/],
    [user("team_owner"), "/desk", /\/desk$/],
    [user(null, true), "/desk", /\/desk$/],
    [user("custom_staff"), "/desk", /\/osint$/],
    [user("recruiter"), "/desk/roles", /\/desk\/sourcing-leads$/],
  ] as const;

  for (const [identity, source, expected] of cases) {
    const context = await browser.newContext();
    const page = await context.newPage();
    await mockIdentity(page, identity);
    await page.goto(source, { waitUntil: "domcontentloaded" });
    await expect(page, `${identity.role_name ?? "candidate"} from ${source}`).toHaveURL(expected);
    await context.close();
  }
});

test("OSINT tiers survive the login round-trip", async ({ browser }) => {
  const context = await browser.newContext();
  const page = await context.newPage();
  let authenticated = false;
  const identity = user("recruiter");

  await page.route("**/api/auth/me", (route) =>
    authenticated
      ? route.fulfill({ json: identity })
      : route.fulfill({ status: 401, json: { detail: "Unauthorized" } }),
  );
  await page.route("**/api/auth/login", async (route) => {
    authenticated = true;
    await route.fulfill({
      json: { success: true, data: { user: identity, message: "Login successful" } },
    });
  });

  await page.goto("/osint?tiers=tier1%2Ctier3");
  await expect(page).toHaveURL(/\/login\?redirect=.*tiers/);
  await page.getByLabel("Email").fill(identity.email);
  await page.getByLabel("Password").fill("IntegrationTest123");
  await page.getByRole("button", { name: "Sign In" }).click();
  await expect(page).toHaveURL(/\/osint\?tiers=tier1%2Ctier3$/);
  await expect(page.getByRole("heading", { name: "Look someone up" })).toBeVisible();
  await context.close();
});

test("every Desk page and Signals render for a superuser", async ({ page }) => {
  for (const route of deskRoutes) {
    const response = await page.goto(route, { waitUntil: "domcontentloaded" });
    expect(response?.status(), route).toBeLessThan(400);
    await expect(page.getByText("Desk", { exact: true }).first(), route).toBeVisible();
    await expect(page.getByText(/404|not found/i), route).toHaveCount(0);
  }

  const users = unwrap<{ items: { id: string }[] }>(
    await (await page.request.get("/api/admin/users?limit=1")).json(),
  );
  expect(users.items.length).toBeGreaterThan(0);
  const detailRoute = `/desk/users/${users.items[0].id}`;
  const detailResponse = await page.goto(detailRoute, { waitUntil: "domcontentloaded" });
  expect(detailResponse?.status(), detailRoute).toBeLessThan(400);
  await expect(page.getByText(/404|not found/i), detailRoute).toHaveCount(0);

  await page.goto("/desk/signals");
  await expect(page.getByRole("heading", { name: "Signals", exact: true })).toBeVisible();
});

test("MFA and impersonation complete a full start/status/end lifecycle", async ({ page }) => {
  const usersResponse = await page.request.get("/api/admin/users?limit=100");
  expect(usersResponse.ok()).toBeTruthy();
  const users = unwrap<{ items: { id: string; email: string }[] }>(await usersResponse.json());
  const candidate = users.items.find((item) => item.email === CANDIDATE_EMAIL);
  expect(candidate).toBeTruthy();

  const enrollResponse = await page.request.post("/api/admin/mfa/enroll");
  expect(enrollResponse.ok()).toBeTruthy();
  const enrollment = unwrap<{ secret: string }>(await enrollResponse.json());
  const code = execFileSync(
    "python3",
    ["-c", "import pyotp,sys; print(pyotp.TOTP(sys.argv[1]).now())", enrollment.secret],
    { encoding: "utf8" },
  ).trim();

  const confirmResponse = await page.request.post("/api/admin/mfa/confirm", { data: { code } });
  expect(confirmResponse.status()).toBe(200);
  let status = unwrap<{ mfaEnabled: boolean }>(
    await (await page.request.get("/api/admin/mfa/status")).json(),
  );
  expect(status.mfaEnabled).toBe(true);

  const impersonationResponse = await page.request.post(
    `/api/admin/impersonation/start/${candidate!.id}`,
    { data: { reason: "T4 browser lifecycle validation", mfa_code: code } },
  );
  expect(impersonationResponse.ok()).toBeTruthy();
  let impersonation = unwrap<{ isImpersonating: boolean; targetUserId: string }>(
    await (await page.request.get("/api/admin/impersonation/status")).json(),
  );
  expect(impersonation).toMatchObject({
    isImpersonating: true,
    targetUserId: candidate!.id,
  });

  const endResponse = await page.request.post("/api/admin/impersonation/end");
  expect(endResponse.status()).toBe(200);
  const endedStatusResponse = await page.request.get("/api/admin/impersonation/status");
  const endedStatusBody = await endedStatusResponse.json();
  expect(
    endedStatusResponse.ok(),
    `status after end returned ${endedStatusResponse.status()}: ${JSON.stringify(endedStatusBody)}`,
  ).toBe(true);
  impersonation = unwrap<{ isImpersonating: boolean; targetUserId: string }>(endedStatusBody);
  expect(impersonation.isImpersonating).toBe(false);

  const disableResponse = await page.request.post("/api/admin/mfa/disable");
  expect(disableResponse.status()).toBe(200);
  status = unwrap<{ mfaEnabled: boolean }>(
    await (await page.request.get("/api/admin/mfa/status")).json(),
  );
  expect(status.mfaEnabled).toBe(false);
});

test("responsive AppShell product chips match Candidate, Desk, and OSINT", async ({
  browser,
}, testInfo) => {
  const shots = [
    ["candidate-desktop", { width: 1440, height: 900 }, user(null), "/app/matches", "Candidate"],
    ["desk-tablet", { width: 820, height: 1180 }, user(null, true), "/desk/system-health", "Desk"],
    ["osint-mobile", { width: 390, height: 844 }, user("recruiter"), "/osint", "OSINT"],
  ] as const;

  for (const [name, viewport, identity, route, chip] of shots) {
    const context = await browser.newContext({ viewport });
    const page = await context.newPage();
    await mockIdentity(page, identity);
    await page.goto(route);
    await expect(page.locator("header").getByText(chip, { exact: true })).toBeVisible();
    await page.screenshot({
      path: testInfo.outputPath("screenshots", `${name}.png`),
      fullPage: true,
    });
    await context.close();
  }
});
