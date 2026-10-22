import { mkdirSync, writeFileSync } from "node:fs";
import os from "node:os";
import type {
  Reporter,
  TestCase,
  TestResult,
  FullResult,
} from "@playwright/test/reporter";

export default class SafeReporter implements Reporter {
  rows: object[] = [];
  onTestEnd(test: TestCase, result: TestResult) {
    const row = {
      test: test.titlePath(),
      status: result.status,
      duration_ms: result.duration,
      browser: test.annotations
        .filter((a) => a.type === "browser")
        .map((a) => a.description),
    };
    this.rows.push(row);
    console.log(JSON.stringify(row));
    for (const error of result.errors) {
      const safe = (error.message ?? "Browser assertion failed")
        .replace(/eyJ[A-Za-z0-9_.-]+/g, "[redacted-token]")
        .replace(
          /(code|state|nonce|token|secret|password|cookie)=([^\s&]+)/gi,
          "$1=[redacted]",
        );
      console.error(safe.slice(0, 4000));
      const location = error.stack?.match(
        /(?:pilot|smoke)\.spec\.ts:\d+:\d+/,
      )?.[0];
      if (location) console.error(location);
    }
  }
  onError() {
    console.error(
      "Synthetic browser harness error; inspect fixture locally without exporting credentials.",
    );
  }
  onEnd(result: FullResult) {
    mkdirSync("../.local/phase7", { recursive: true });
    writeFileSync(
      "../.local/phase7/browser.json",
      JSON.stringify(
        {
          release_sha: process.env.RELEASE_SHA,
          date: new Date().toISOString(),
          tester: "GitHub Actions / Playwright automation",
          runtime: {
            node: process.version,
            platform: os.platform(),
            cpus: os.cpus().length,
            memory_bytes: os.totalmem(),
          },
          status: result.status,
          tests: this.rows,
          limitations:
            "Synthetic loopback OIDC, fixture scanner, local originals, development frontend; no real staging/customer approval",
        },
        null,
        2,
      ),
    );
  }
}
