"""Reject incomplete/misattributed synthetic measurements; never declares pilot GO."""

import json
import os
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1] / ".local/phase7"
    values = {
        name: json.loads((root / f"{name}.json").read_text())
        for name in ("browser", "capacity", "resources")
    }
    expected = os.environ["RELEASE_SHA"]
    assert all(v["release_sha"] == expected for v in values.values())
    assert values["browser"]["status"] == "passed"
    assert all(t["status"] == "passed" for t in values["browser"]["tests"])
    assert values["capacity"]["verdict"] == "OBSERVED_SYNTHETIC_ENVELOPE_ONLY"
    assert values["resources"]["metadata"]["schema"] == "0009"
    assert values["resources"]["metadata"]["commit_tracking"] == "on"
    samples = values["resources"]["samples"]
    assert samples and any(s["backend_processes"] >= 2 for s in samples)
    assert any(s["backend_rss_bytes"] > 0 for s in samples)
    assert any(s["original_and_temp_bytes"] > 0 for s in samples)
    assert values["capacity"]["latencies"]
    print(
        json.dumps(
            {"synthetic_evidence": "PASS", "release_sha": expected, "pilot": "NO-GO"}
        )
    )


if __name__ == "__main__":
    main()
