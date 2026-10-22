"""One-time snapshot discovery; final required CI uses an explicit checksum pin."""

import json
import re
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import quote

entries = json.loads(Path(sys.argv[1]).read_text())
if not isinstance(entries, list) or not entries:
    raise ValueError("Missing official advisory database metadata")
entry = entries[0]
checksum, path = entry["checksum"], entry["path"]
if not re.fullmatch(r"sha256:[a-f0-9]{64}", checksum):
    raise ValueError("Advisory database checksum required")
if not re.fullmatch(r"vulnerability-db_v6\.[0-9.]+_[0-9TZ:._-]+\.tar\.zst", path):
    raise ValueError("Unexpected advisory database archive")
built = datetime.fromisoformat(entry["built"].replace("Z", "+00:00"))
if not timedelta(0) <= datetime.now(UTC) - built <= timedelta(hours=120):
    raise ValueError("Advisory database snapshot is stale or future-dated")
url = (
    "https://grype.anchore.io/databases/v6/"
    + path
    + "?checksum="
    + quote(checksum, safe="")
)
print(
    json.dumps(
        {"url": url, "checksum": checksum, "built": entry["built"], "path": path},
        sort_keys=True,
    )
)
Path(sys.argv[2]).write_text(url)
