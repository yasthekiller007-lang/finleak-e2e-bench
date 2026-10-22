"""Produce a small safe test summary instead of exporting raw test/debug JSON."""

import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path


def main():
    directory = Path(__file__).resolve().parents[1] / ".local/phase7"
    raw = json.loads((directory / "frontend-raw.json").read_text())
    assert raw["success"] and raw["numFailedTests"] == 0
    assert raw["numPendingTests"] == 0 and raw["numPassedTests"] == raw["numTotalTests"]
    (directory / "frontend.json").write_text(
        json.dumps(
            {
                "release_sha": os.environ["RELEASE_SHA"],
                "date": datetime.now(UTC).isoformat(),
                "tester": "GitHub Actions / Vitest",
                "node": subprocess.check_output(
                    ["node", "--version"], text=True
                ).strip(),
                "summary": {"passed": raw["numPassedTests"], "skipped": 0, "failed": 0},
                "scope": "jsdom/component/proxy; separate Playwright browser evidence",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
