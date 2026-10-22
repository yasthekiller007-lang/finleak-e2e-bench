import { defineConfig } from "@playwright/test";

const discovery = process.argv.includes("--list");
if (
  !discovery &&
  (process.env.GITHUB_ACTIONS !== "true" || process.env.P0_EXECUTION !== "1")
)
  throw new Error(
    "A separately authorized synthetic GitHub Actions job is required",
  );

export default defineConfig({
  testDir: "./p0-acceptance",
  testMatch: "financial.spec.ts",
  workers: 1,
  retries: 0,
  timeout: 140000,
  expect: { timeout: 15000 },
  reporter: [["./p0-acceptance/reporter.ts"]],
  use: {
    baseURL: "http://127.0.0.1:3000",
    browserName: "chromium",
    trace: "off",
    screenshot: "off",
    video: "off",
  },
  // Services belong to the bounded orchestrator; discovery cannot start any.
});
