import { mkdirSync, writeFileSync } from "node:fs";
import type {
  Reporter,
  TestCase,
  TestResult,
  FullResult,
  FullConfig,
  Suite,
} from "@playwright/test/reporter";
export default class SafeReporter implements Reporter {
  rows: object[] = [];
  discovered = 0;
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
    console.error(
      "Product acceptance infrastructure error. No credentials or raw auth details exported.",
    );
  }
  onEnd(result: FullResult) {
    const discovery = process.argv.includes("--list");
    const verdict = discovery
      ? "DISCOVERY_ONLY"
      : this.rows.length === 0
        ? "NOT_EXECUTED"
        : result.status === "passed"
          ? "PASS_E2E_CANDIDATE"
          : "FAIL";
    mkdirSync("../.local/product-v11", { recursive: true });
    writeFileSync(
      "../.local/product-v11/browser-results.json",
      JSON.stringify(
        {
          status: verdict,
          discovered_tests: this.discovered,
          tests_executed: this.rows.length,
          tests: this.rows,
          synthetic: true,
          qualification: false,
          scope:
            "OIDC test realm and PostgreSQL development acceptance; no scanner, import or PITR qualification",
        },
        null,
        2,
      ),
    );
    console.log(
      `Product acceptance: ${verdict}; ${this.rows.length} tests executed`,
    );
  }
}
