import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { test as setup } from "@playwright/test";

const BACKEND_ROOT = path.resolve(__dirname, "../../../backend");
const TEST_EMAIL = process.env.INTEGRATION_TEST_EMAIL ?? "e2e-integration@example.com";
const TEST_PASSWORD = process.env.INTEGRATION_TEST_PASSWORD ?? "IntegrationTest123";

const AUTH_FILE = path.resolve(__dirname, ".auth/user.json");

function pythonExecutable(): string {
  if (process.platform === "win32") return "python";
  const venvPython = path.join(BACKEND_ROOT, ".venv", "bin", "python");
  if (fs.existsSync(venvPython)) return venvPython;
  return "python3";
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

setup("authenticate against live backend", async ({ page }) => {
  await pollBackendHealth();

  // The real register -> verify-email -> login flow requires clicking a link
  // sent by email. For integration tests we skip straight to a verified
  // staff user by writing the DB row directly (mirrors backend/tests fixtures),
  // then log in over HTTP like a normal client to obtain real cookies. This
  // suite exercises staff-only OSINT routes; role-specific coverage is separate.
  execFileSync(
    pythonExecutable(),
    [
      "scripts/create_test_user.py",
      "--email",
      TEST_EMAIL,
      "--password",
      TEST_PASSWORD,
      "--is-superuser",
    ],
    {
      cwd: BACKEND_ROOT,
      stdio: ["ignore", "pipe", "inherit"],
      // Host .env may be production-like; scripts only need DB access.
      env: {
        ...process.env,
        APP_ENV: "development",
        COOKIE_SECURE: "false",
        ALLOW_E2E_SUPERUSER_BOOTSTRAP: "1",
      },
    },
  );

  const response = await page.request.post("/api/auth/login", {
    data: { email: TEST_EMAIL, password: TEST_PASSWORD },
  });

  if (!response.ok()) {
    throw new Error(
      `Integration auth setup failed to log in as ${TEST_EMAIL}: ${response.status()} ${await response.text()}`,
    );
  }

  await page.context().storageState({ path: AUTH_FILE });
});
