import { defineConfig } from "@playwright/test";
if (
  process.env.PRODUCT_V11_ACCEPTANCE !== "1" ||
  process.env.PRODUCT_SYNTHETIC_ACCOUNTS_ONLY !== "1" ||
  process.env.FLA_ENVIRONMENT !== "test"
)
  throw new Error("Explicit isolated synthetic product acceptance is required");
const url = new URL(
  process.env.PRODUCT_FRONTEND_URL ?? "http://127.0.0.1:3000",
);
if (
  !["127.0.0.1", "localhost", "[::1]"].includes(url.hostname) ||
  url.username ||
  url.password ||
  !["http:", "https:"].includes(url.protocol)
)
  throw new Error(
    "Only an already-authorized loopback development frontend is allowed",
  );
export default defineConfig({
  testDir: "./product-acceptance",
  workers: 1,
  retries: 0,
  timeout: 120000,
  reporter: [["./product-acceptance/safe-reporter.ts"]],
  use: { baseURL: url.origin, trace: "off", video: "off", screenshot: "off" },
  // No webServer/globalSetup: this configuration creates no service or resource.
});
