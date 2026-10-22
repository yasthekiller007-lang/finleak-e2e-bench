/** Optional Cloud development profile; historical config/assertions remain untouched.
 * Scheduling budgets are not application timeouts or performance qualification.
 */
import { defineConfig, mergeConfig } from "vitest/config";
import base from "./vitest.config";
export default mergeConfig(
  base,
  defineConfig({
    test: {
      maxWorkers: 1,
      testTimeout: 15000,
      setupFiles: ["./tests/product-v19-cloud-setup.ts"],
    },
  }),
);
