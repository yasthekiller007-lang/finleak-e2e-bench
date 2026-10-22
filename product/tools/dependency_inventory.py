"""Exact lockfile inventories for offline advisory matching; no customer data."""

import hashlib
import json
import sys
import tomllib
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]


def inventories(root=ROOT):
    python_lock = root / "backend/uv.lock"
    npm_lock = root / "frontend/package-lock.json"
    python = sorted(
        {
            "pkg:pypi/"
            + quote(item["name"].lower().replace("_", "-"), safe="")
            + "@"
            + quote(item["version"], safe="")
            for item in tomllib.loads(python_lock.read_text())["package"]
            if "virtual" not in item.get("source", {})
            and "editable" not in item.get("source", {})
        }
    )
    npm = set()
    for path, item in json.loads(npm_lock.read_text())["packages"].items():
        if not path or not item.get("version") or "node_modules/" not in path:
            continue
        name = path.rsplit("node_modules/", 1)[1]
        npm.add(
            "pkg:npm/" + quote(name, safe="/") + "@" + quote(item["version"], safe="")
        )
    npm = sorted(npm)
    if not python or not npm:
        raise ValueError("Incomplete dependency inventories")
    return {"python": python, "npm": npm}, {
        "profile": "pilot-supply-chain/1",
        "scope": "all locked versions, including dev/platform alternatives",
        "lock_sha256": {
            str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (python_lock, npm_lock)
        },
        "packages": {"python": len(python), "npm": len(npm)},
    }


def main():
    directory = Path(sys.argv[1])
    directory.mkdir(parents=True, exist_ok=True)
    values, report = inventories()
    for kind, packages in values.items():
        (directory / f"{kind}.purl").write_text("\n".join(packages) + "\n")
    (directory / "locked-inventory.json").write_text(json.dumps(report, sort_keys=True))
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
