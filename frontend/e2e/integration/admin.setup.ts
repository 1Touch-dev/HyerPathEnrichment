import { execFileSync } from "node:child_process";
import path from "node:path";
import { test as setup } from "@playwright/test";

const BACKEND_ROOT = path.resolve(__dirname, "../../../backend");
const ADMIN_TEST_EMAIL =
  process.env.INTEGRATION_ADMIN_TEST_EMAIL ?? "e2e-integration-admin@example.com";
const ADMIN_TEST_PASSWORD =
  process.env.INTEGRATION_ADMIN_TEST_PASSWORD ?? "IntegrationAdminTest123";

const AUTH_FILE = path.resolve(__dirname, ".auth/admin-user.json");

function pythonExecutable(): string {
  return process.platform === "win32" ? "python" : "python3";
}

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

setup("authenticate as superuser against live backend", async ({ page }) => {
  await pollBackendHealth();

  // Same direct-DB-row pattern as auth.setup.ts, but with --is-superuser so
  // this session can reach every /app/admin/* page without a 403 redirect.
  execFileSync(
    pythonExecutable(),
    [
      "scripts/create_test_user.py",
      "--email",
      ADMIN_TEST_EMAIL,
      "--password",
      ADMIN_TEST_PASSWORD,
      "--is-superuser",
    ],
    { cwd: BACKEND_ROOT, stdio: ["ignore", "pipe", "inherit"] },
  );

  const response = await page.request.post("/api/auth/login", {
    data: { email: ADMIN_TEST_EMAIL, password: ADMIN_TEST_PASSWORD },
  });

  if (!response.ok()) {
    throw new Error(
      `Integration admin auth setup failed to log in as ${ADMIN_TEST_EMAIL}: ${response.status()} ${await response.text()}`,
    );
  }

  // Saved to a separate file from the regular-user session (.auth/user.json)
  // so the "integration" project's non-admin tests are unaffected.
  await page.context().storageState({ path: AUTH_FILE });
});
