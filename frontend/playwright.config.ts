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
      name: "integration",
      testMatch: "integration/**/*.spec.ts",
      use: {
        ...devices["Desktop Chrome"],
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
