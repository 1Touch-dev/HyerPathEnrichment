import { test, expect, type Page } from "@playwright/test";

const BACKEND_URL = (process.env.BACKEND_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
const AUTHENTICATED_SHELL_TIMEOUT = 30_000;

async function expectAuthenticatedShell(page: Page, product: "Candidate" | "Desk"): Promise<void> {
  await expect(page.locator("header").getByText(product, { exact: true }).first()).toBeVisible({
    timeout: AUTHENTICATED_SHELL_TIMEOUT,
  });
}

async function gotoDesk(page: Page, route: string): Promise<void> {
  const response = await page.goto(route);
  expect(response?.status(), route).toBeLessThan(400);
  await expectAuthenticatedShell(page, "Desk");
}

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

test.describe("Desk pages (live backend, superuser session)", () => {
  test("/desk renders the owner landing without an error state", async ({ page }) => {
    await gotoDesk(page, "/desk");
    await expect(page).toHaveURL(/\/desk$/, { timeout: 15_000 });
    await expect(page.getByRole("heading", { name: "Self-checks" })).toBeVisible();
    await expect(page.getByText("System health unavailable")).toHaveCount(0);
  });

  test("/desk/system-health renders database + redis self-checks", async ({ page }) => {
    await gotoDesk(page, "/desk/system-health");
    await expect(page.getByRole("heading", { name: "Self-checks" })).toBeVisible();
    await expect(page.getByText("Database", { exact: true })).toBeVisible();
    await expect(page.getByText("Redis", { exact: true })).toBeVisible();
    await expect(page.getByText("System health unavailable")).toHaveCount(0);
  });

  test("/desk/analytics renders job match analytics", async ({ page }) => {
    await gotoDesk(page, "/desk/analytics");
    await expect(page.getByRole("heading", { name: "Job match analytics" })).toBeVisible();
    await expect(page.getByText("No analytics available")).toHaveCount(0);
  });

  test("/desk/audit-logs renders audit log table", async ({ page }) => {
    await gotoDesk(page, "/desk/audit-logs");
    await expect(page.getByRole("heading", { name: "Audit logs", exact: true })).toBeVisible();
  });

  test("/desk/brands renders Brands heading", async ({ page }) => {
    await gotoDesk(page, "/desk/brands");
    await expect(page.getByRole("heading", { name: "Brands", exact: true })).toBeVisible();
  });

  test("/desk/feature-flags renders feature flags panel", async ({ page }) => {
    await gotoDesk(page, "/desk/feature-flags");
    await expect(page.getByRole("heading", { name: "Feature flags", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Create flag" })).toBeVisible();
  });

  test("/desk/queues renders queue monitor", async ({ page }) => {
    await gotoDesk(page, "/desk/queues");
    await expect(page.getByRole("heading", { name: "Queues", exact: true })).toBeVisible();
  });

  test("/desk/roles renders role/permission matrix", async ({ page }) => {
    await gotoDesk(page, "/desk/roles");
    await expect(page.getByRole("heading", { name: "Roles", exact: true })).toBeVisible();
    // Migration 038 seeds "admin" + "support" roles — this should never be the empty state.
    await expect(page.getByText("No roles configured")).toHaveCount(0);
  });

  test("/desk/users renders users table", async ({ page }) => {
    await gotoDesk(page, "/desk/users");
    await expect(page.getByRole("heading", { name: "Users", exact: true })).toBeVisible();
    // The logged-in superuser itself is always in the list.
    await expect(page.getByText("No users found")).toHaveCount(0);
  });

  test("/app/settings/security renders MFA setup card", async ({ page }) => {
    await page.goto("/app/settings/security");
    await expectAuthenticatedShell(page, "Candidate");
    await expect(page.getByRole("heading", { name: "Security", exact: true })).toBeVisible();
    await expect(page.getByText("Two-factor authentication")).toBeVisible();
  });
});
