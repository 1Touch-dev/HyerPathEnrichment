import { defineConfig, devices } from "@playwright/test";

process.env.FRONTEND_USE_MOCKS = process.env.FRONTEND_USE_MOCKS ?? "true";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: "http://127.0.0.1:3000",
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
      testIgnore: ["integration/auth.setup.ts", "integration/admin.setup.ts", "integration/admin.spec.ts"],
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
    command: "npm run dev",
    url: "http://127.0.0.1:3000",
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
    env: {
      ...process.env,
      FRONTEND_USE_MOCKS: process.env.FRONTEND_USE_MOCKS ?? "true",
      BACKEND_API_URL: process.env.BACKEND_API_URL ?? "http://localhost:8000",
      BACKEND_API_TOKEN: process.env.BACKEND_API_TOKEN ?? "change-me",
    },
  },
});
