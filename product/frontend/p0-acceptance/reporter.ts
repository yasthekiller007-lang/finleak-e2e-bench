import { mkdirSync, writeFileSync } from "node:fs";
import type {
  Reporter,
  TestCase,
  TestResult,
  FullResult,
  FullConfig,
  Suite,
} from "@playwright/test/reporter";

export default class SafeP0Reporter implements Reporter {
  discovered = 0;
  rows: { test: string; status: string; duration_ms: number }[] = [];
  onBegin(_config: FullConfig, suite: Suite) {
    this.discovered = suite.allTests().length;
  }
  onTestEnd(test: TestCase, result: TestResult) {
    this.rows.push({
      test: test.title,
      status: result.status,
      duration_ms: result.duration,
    });
  }
  onError() {
    console.error("P0 acceptance error; raw authentication details withheld");
  }
  onEnd(result: FullResult) {
    const status = process.argv.includes("--list")
      ? "DISCOVERY_ONLY"
      : result.status === "passed" &&
          this.rows.length === 1 &&
          this.discovered === 1
        ? "PASS"
        : "FAIL";
    mkdirSync("../.local/p0-evidence", { recursive: true });
    writeFileSync(
      "../.local/p0-evidence/browser.json",
      JSON.stringify(
        {
          status,
          discovered: this.discovered,
          executed: this.rows.length,
          tests: this.rows,
          retries: 0,
          synthetic: true,
          phase7_qualified: false,
        },
        null,
        2,
      ) + "\n",
    );
    console.log(`P0 browser: ${status}; ${this.rows.length} executed`);
  }
}
