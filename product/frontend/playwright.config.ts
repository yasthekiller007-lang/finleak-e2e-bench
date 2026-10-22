import { randomBytes } from "node:crypto";
import { defineConfig, devices } from "@playwright/test";

if (
  process.env.PHASE7_SYNTHETIC_ACCEPTANCE !== "1" ||
  process.env.FLA_ENVIRONMENT !== "test"
)
  throw new Error("Only explicit disposable synthetic acceptance is permitted");

const fixtureEnv = {
  ...process.env,
  BACKEND_URL: "http://127.0.0.1:8000",
  NEXTAUTH_URL: "http://127.0.0.1:3000",
  NEXTAUTH_SECRET: randomBytes(32).toString("hex"),
  OIDC_ISSUER_URL: "http://127.0.0.1:9001",
  OIDC_AUDIENCE: "synthetic-phase7-api",
  OIDC_CLIENT_ID: "synthetic-phase7-browser",
  OIDC_CLIENT_SECRET: randomBytes(32).toString("hex"),
  NEXT_TELEMETRY_DISABLED: "1",
};

export default defineConfig({
  testDir: "./e2e",
  workers: 1,
  retries: 0,
  timeout: 60000,
  expect: { timeout: 20000 },
  reporter: [["./e2e/safe-reporter.ts"]],
  globalSetup: "./e2e/resource-setup.ts",
  globalTeardown: "./e2e/resource-teardown.ts",
  use: {
    baseURL: fixtureEnv.NEXTAUTH_URL,
    viewport: { width: 1366, height: 768 },
    timezoneId: "UTC",
    // Auth network traces can contain fixture credentials. Store only safe summaries.
    trace: "off",
    screenshot: "off",
    video: "off",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
      testMatch: "pilot.spec.ts",
    },
    {
      name: "firefox-smoke",
      use: { ...devices["Desktop Firefox"] },
      testMatch: "smoke.spec.ts",
    },
  ],
  webServer: [
    {
      command:
        "uv run uvicorn acceptance.browser_runtime:provider --factory --host 127.0.0.1 --port 9001 --no-access-log",
      cwd: "../backend",
      url: "http://127.0.0.1:9001/.well-known/openid-configuration",
      env: fixtureEnv,
      reuseExistingServer: false,
    },
    {
      command:
        "uv run uvicorn acceptance.browser_runtime:application --factory --workers 2 --host 127.0.0.1 --port 8000 --no-access-log",
      cwd: "../backend",
      url: "http://127.0.0.1:8000/api/v1/health",
      env: fixtureEnv,
      reuseExistingServer: false,
    },
    {
      command: "npm run dev -- --port 3000",
      url: "http://127.0.0.1:3000/login",
      env: fixtureEnv,
      timeout: 120000,
      reuseExistingServer: false,
    },
  ],
});
