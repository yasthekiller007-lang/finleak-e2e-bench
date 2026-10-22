"""Create a local reviewable projection. No git init, push, account or resource change."""

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def prepare(output):
    output = output.resolve()
    if output.exists() or output.is_relative_to(ROOT):
        raise ValueError("A new output directory outside the source is required")
    names = (
        subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT)
        .decode()
        .split("\0")
    )
    output.mkdir(parents=True)
    manifest = []
    for name in filter(None, names):
        source = ROOT / name
        if not source.is_file() or source.is_symlink():
            raise ValueError("Regular tracked source files required")
        target = output / "product" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        manifest.append(
            {
                "path": "product/" + name,
                "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            }
        )
    workflow = output / ".github/workflows/finleak-p0.yml"
    workflow.parent.mkdir(parents=True)
    shutil.copyfile(ROOT / "bench/p0/finleak-p0.yml", workflow)
    # No billing-evidence.json is created: the example remains explicitly BLOCKED.
    (output / "PROJECTION.json").write_text(
        json.dumps(
            {
                "source_commit": subprocess.check_output(
                    ["git", "rev-parse", "HEAD"], cwd=ROOT
                )
                .decode()
                .strip(),
                "files": manifest,
                "active_workflows": [".github/workflows/finleak-p0.yml"],
                "billing_review": "MISSING",
                "authorization": "NOT_GRANTED",
            },
            indent=2,
        )
        + "\n"
    )
    assert list((output / ".github/workflows").iterdir()) == [workflow]
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    print(prepare(parser.parse_args().output))
