import { defineConfig, devices } from "@playwright/test";

process.env.FRONTEND_USE_MOCKS = process.env.FRONTEND_USE_MOCKS ?? "true";

const playwrightPort = Number(process.env.PLAYWRIGHT_PORT ?? "3100");

if (!Number.isInteger(playwrightPort) || playwrightPort < 1 || playwrightPort > 65_535) {
  throw new Error("PLAYWRIGHT_PORT must be an integer between 1 and 65535");
}

const playwrightBaseURL = `http://127.0.0.1:${playwrightPort}`;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: playwrightBaseURL,
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      testIgnore: "**/integration/**",
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "integration-setup",
      testMatch: "integration/auth.setup.ts",
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "integration",
      testMatch: "integration/**/*.spec.ts",
      testIgnore: [
        "integration/auth.setup.ts",
        "integration/admin.setup.ts",
        "integration/admin.spec.ts",
      ],
      dependencies: ["integration-setup"],
      use: {
        ...devices["Desktop Chrome"],
        storageState: "e2e/integration/.auth/user.json",
      },
    },
    {
      name: "integration-admin-setup",
      testMatch: "integration/admin.setup.ts",
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "integration-admin",
      testMatch: "integration/admin.spec.ts",
      dependencies: ["integration-admin-setup"],
      use: {
        ...devices["Desktop Chrome"],
        storageState: "e2e/integration/.auth/admin-user.json",
      },
    },
  ],
  webServer: {
    command: `npm run dev -- --hostname 127.0.0.1 --port ${playwrightPort}`,
    url: playwrightBaseURL,
    reuseExistingServer: process.env.PLAYWRIGHT_REUSE_SERVER === "true",
    timeout: 120_000,
    env: {
      ...process.env,
      FRONTEND_USE_MOCKS: process.env.FRONTEND_USE_MOCKS ?? "true",
      BACKEND_API_URL: process.env.BACKEND_API_URL ?? "http://localhost:8000",
      BACKEND_API_TOKEN: process.env.BACKEND_API_TOKEN ?? "change-me",
    },
  },
});
