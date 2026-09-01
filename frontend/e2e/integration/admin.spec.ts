import { test, expect } from "@playwright/test";

const BACKEND_URL = (process.env.BACKEND_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

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

test.describe("Admin Module pages (live backend, superuser session)", () => {
  test("/app/admin redirects to system health, no error state", async ({ page }) => {
    await page.goto("/app/admin");
    await expect(page).toHaveURL(/\/app\/admin\/system-health$/, { timeout: 15_000 });
    await expect(page.getByRole("heading", { name: "Self-checks" })).toBeVisible();
    await expect(page.getByText("System health unavailable")).toHaveCount(0);
  });

  test("/app/admin/system-health renders database + redis self-checks", async ({ page }) => {
    await page.goto("/app/admin/system-health");
    await expect(page.getByRole("heading", { name: "Self-checks" })).toBeVisible();
    await expect(page.getByText("Database", { exact: true })).toBeVisible();
    await expect(page.getByText("Redis", { exact: true })).toBeVisible();
    await expect(page.getByText("System health unavailable")).toHaveCount(0);
  });

  test("/app/admin/analytics renders job match analytics", async ({ page }) => {
    await page.goto("/app/admin/analytics");
    await expect(page.getByRole("heading", { name: "Job match analytics" })).toBeVisible();
    await expect(page.getByText("No analytics available")).toHaveCount(0);
  });

  test("/app/admin/audit-logs renders audit log table", async ({ page }) => {
    await page.goto("/app/admin/audit-logs");
    await expect(page.getByRole("heading", { name: "Audit logs", exact: true })).toBeVisible();
  });

  test("/app/admin/brands renders Brands heading", async ({ page }) => {
    await page.goto("/app/admin/brands");
    await expect(page.getByRole("heading", { name: "Brands", exact: true })).toBeVisible();
  });

  test("/app/admin/feature-flags renders feature flags panel", async ({ page }) => {
    await page.goto("/app/admin/feature-flags");
    await expect(page.getByRole("heading", { name: "Feature flags", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Create flag" })).toBeVisible();
  });

  test("/app/admin/queues renders queue monitor", async ({ page }) => {
    await page.goto("/app/admin/queues");
    await expect(page.getByRole("heading", { name: "Queues", exact: true })).toBeVisible();
  });

  test("/app/admin/roles renders role/permission matrix", async ({ page }) => {
    await page.goto("/app/admin/roles");
    await expect(page.getByRole("heading", { name: "Roles", exact: true })).toBeVisible();
    // Migration 038 seeds "admin" + "support" roles — this should never be the empty state.
    await expect(page.getByText("No roles configured")).toHaveCount(0);
  });

  test("/app/admin/users renders users table", async ({ page }) => {
    await page.goto("/app/admin/users");
    await expect(page.getByRole("heading", { name: "Users", exact: true })).toBeVisible();
    // The logged-in superuser itself is always in the list.
    await expect(page.getByText("No users found")).toHaveCount(0);
  });

  test("/app/settings/security renders MFA setup card", async ({ page }) => {
    await page.goto("/app/settings/security");
    await expect(page.getByRole("heading", { name: "Security", exact: true })).toBeVisible();
    await expect(page.getByText("Two-factor authentication")).toBeVisible();
  });
});
