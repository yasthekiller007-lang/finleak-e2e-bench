"""Read-only exact-image verification of the upstream-built replacement library."""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

COMMIT = "df84af25dc1942490e1d1c899a07619152a46148"


def command(*args):
    return subprocess.check_output(["docker", *args], timeout=30).decode().strip()


def main():
    sha = os.environ["RELEASE_SHA"]
    if not re.fullmatch("[a-f0-9]{40}", sha) or len(sys.argv) != 5:
        raise ValueError("Exact release and three image inventories required")
    results = []
    for image in sys.argv[2:]:
        if not re.fullmatch("phase7-(backend|frontend|scanner):advisory", image):
            raise ValueError("Unqualified image")
        if (
            command(
                "inspect",
                "--format",
                '{{index .Config.Labels "org.opencontainers.image.revision"}}',
                image,
            )
            != sha
        ):
            raise ValueError("Wrong runtime revision")
        output = command(
            "run",
            "--rm",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--entrypoint",
            "sh",
            image,
            "-c",
            "cat /usr/share/pilot/zlib-patch.json; sha256sum /usr/lib/libz.so.1; "
            "test ! -f /lib/libz.so.1",
        )
        metadata, actual = output.splitlines()
        metadata = json.loads(metadata)
        if (
            metadata["profile"] != "pilot-zlib-patch/1"
            or metadata["source_commit"] != COMMIT
            or metadata["path"] != "/usr/lib/libz.so.1"
            or metadata["library_sha256"] != actual.split()[0]
            or not re.fullmatch("[a-f0-9]{64}", metadata["library_sha256"])
        ):
            raise ValueError("Replacement library does not match pinned build")
        results.append(
            {
                "image": image,
                "image_id": command("inspect", "--format", "{{.Id}}", image),
                **metadata,
            }
        )
    evidence = {
        "result": "PASS",
        "kind": "patched-zlib-runtime",
        "release_sha": sha,
        "images": results,
    }
    Path(sys.argv[1]).write_text(json.dumps(evidence, sort_keys=True))
    print(json.dumps(evidence, sort_keys=True))


if __name__ == "__main__":
    main()
