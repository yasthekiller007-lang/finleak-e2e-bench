"""Bounded source pattern scan; reports locations/rules without printing values."""
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RULES = {
    "private-key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "github-token": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b"),
    "aws-access-key": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "openai-token": re.compile(r"\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{32,}\b"),
    "credential-url": re.compile(r"[a-z][a-z0-9+.-]*://[^\s'\"/:]+:([^\s'\"/@]+)@", re.I),
    "literal-secret": re.compile(r"\b(?:api_key|client_secret|nextauth_secret|password)\s*[:=]\s*['\"]([^'\"]{8,})['\"]", re.I),
}


def main():
    output = subprocess.check_output(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=ROOT)
    files = sorted(set(name for name in output.decode().split("\0") if name))
    findings = []
    for name in files:
        path = ROOT / name
        if not path.is_file():
            continue
        try:
            contents = path.read_text()
        except UnicodeDecodeError:
            continue
        for rule, pattern in RULES.items():
            for match in pattern.finditer(contents):
                if rule == "credential-url" and match[1] in {"PASSWORD", "${{ github.run_id }}"}:
                    continue  # Explicit templates/disposable runner credential; never actual credentials.
                if rule == "literal-secret" and match[1].startswith(("fixture-", "synthetic-")):
                    continue
                findings.append((name, contents.count("\n", 0, match.start())+1, rule))
    for name, line, rule in findings:
        print(f"{name}:{line}: {rule}")
    print(f"Scanned {len(files)} source files; {len(findings)} findings. Pattern coverage is bounded.")
    return bool(findings)


if __name__ == "__main__":
    raise SystemExit(main())
