import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_lock_inventories_include_exact_versions_scoped_packages_and_transitives():
    inventories, report = load("dependency_inventory").inventories()
    assert all(value.startswith("pkg:pypi/") and "@" in value for value in inventories["python"])
    assert any(value.startswith("pkg:npm/%40") for value in inventories["npm"])
    assert len(inventories["python"]) > 40 and len(inventories["npm"]) > 400
    assert len(set(inventories["npm"])) == len(inventories["npm"])
    assert len(report["lock_sha256"]) == 2


@pytest.mark.parametrize("severity", ["High", "Critical"])
def test_advisory_gate_does_not_ignore_unfixed_runtime_or_dev_high_findings(severity):
    result = load("advisory_gate").review(
        {
            "descriptor": {"name": "grype"},
            "matches": [
                {
                    "artifact": {
                        "name": "synthetic",
                        "version": "1.2.3",
                        "metadata": {"dev": True},
                    },
                    "vulnerability": {
                        "id": "CVE-SYNTHETIC",
                        "severity": severity,
                        "fix": {"versions": [], "state": "not-fixed"},
                    },
                }
            ],
        }
    )
    assert result["result"] == "BLOCKED" and len(result["blockers"]) == 1
    assert result["blockers"][0]["version"] == "1.2.3"


@pytest.mark.parametrize(
    "report",
    [
        {},
        {"matches": []},
        {"matches": None},
        {
            "descriptor": {"name": "grype"},
            "matches": [
                {"artifact": {"name": "synthetic"}, "vulnerability": {"severity": "invented"}}
            ],
        },
    ],
)
def test_incomplete_or_unknown_advisory_scan_cannot_be_reported_clean(report):
    with pytest.raises((ValueError, TypeError, KeyError)):
        load("advisory_gate").review(report)


def scoped_policy():
    import json

    return json.loads((ROOT / "tools/advisory_reviews.json").read_text())["reviews"][0]


def brace_match(**changes):
    match = {
        "artifact": {"name": "braces", "version": "3.0.3"},
        "vulnerability": {
            "id": "GHSA-vfj7-8cjw-p6xm",
            "severity": "High",
            "fix": {"versions": []},
        },
    }
    for key, value in changes.items():
        (match["artifact"] if key in {"name", "version"} else match["vulnerability"])[key] = value
    return {"descriptor": {"name": "grype"}, "matches": [match]}


def test_scoped_review_is_visible_and_not_a_clean_or_fixed_finding():
    result = load("advisory_gate").review(brace_match(), scoped_review=scoped_policy())
    assert result["result"] == "REVIEWED NON-RUNTIME FINDING"
    assert result["counts"] == {"high": 1}
    assert result["remaining_findings_require_review"] and result["reviewed"]
    assert load("advisory_gate").review(brace_match())["blockers"]


@pytest.mark.parametrize(
    "change",
    [
        {"version": "3.0.2"},
        {"name": "other"},
        {"id": "other"},
        {"severity": "Critical"},
        {"fix": {"versions": ["3.0.4"]}},
    ],
)
def test_scope_review_cannot_hide_other_or_runtime_fixable_findings(change):
    assert load("advisory_gate").review(brace_match(**change), scoped_review=scoped_policy())[
        "blockers"
    ]


def test_expired_review_blocks():
    policy = {**scoped_policy(), "expires": "2000-01-01T00:00:00Z"}
    assert load("advisory_gate").review(brace_match(), scoped_review=policy)["blockers"]


def runtime_evidence():
    return {
        "result": "PASS",
        "kind": "frontend-dev-glob-absence",
        "release_sha": "a" * 40,
        "files": 100,
        "bytes": 400,
        "forbidden": ["braces", "micromatch", "fast-glob"],
    }


def test_review_requires_same_head_runtime_and_current_development_scope(tmp_path):
    import json
    import shutil

    gate = load("advisory_gate")
    assert gate.qualify_review(ROOT, runtime_evidence(), "a" * 40) == scoped_policy()
    for evidence in (
        {},
        {**runtime_evidence(), "release_sha": "b" * 40},
        {**runtime_evidence(), "files": 0},
        {**runtime_evidence(), "forbidden": []},
    ):
        with pytest.raises(ValueError):
            gate.qualify_review(ROOT, evidence, "a" * 40)
    for file in (
        "frontend/package-lock.json",
        "frontend/eslint.config.mjs",
        "tools/advisory_reviews.json",
        "docs/phase7-dependency-review.md",
    ):
        target = tmp_path / file
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / file, target)
    lock_path = tmp_path / "frontend/package-lock.json"
    lock = json.loads(lock_path.read_text())
    lock["packages"]["node_modules/braces"]["dev"] = False
    lock_path.write_text(json.dumps(lock))
    with pytest.raises(ValueError, match="scope changed"):
        gate.qualify_review(tmp_path, runtime_evidence(), "a" * 40)
    shutil.copy(ROOT / "frontend/package-lock.json", lock_path)
    (tmp_path / "frontend/eslint.config.mjs").write_text('const rootDir = "customer-pattern"')
    with pytest.raises(ValueError, match="input scope changed"):
        gate.qualify_review(tmp_path, runtime_evidence(), "a" * 40)


def test_custom_patch_review_requires_actual_three_same_head_library_inventories():
    gate = load("advisory_gate")
    images = [
        {
            "image": "phase7-" + name + ":advisory",
            "image_id": "sha256:" + "a" * 64,
            "profile": "pilot-zlib-patch/1",
            "source_commit": "df84af25dc1942490e1d1c899a07619152a46148",
            "path": "/usr/lib/libz.so.1",
            "library_sha256": "b" * 64,
        }
        for name in ("backend", "frontend", "scanner")
    ]
    valid = {
        "result": "PASS",
        "kind": "patched-zlib-runtime",
        "release_sha": "a" * 40,
        "images": images,
    }
    gate.qualify_zlib(valid, "a" * 40)
    for invalid in (
        {},
        {**valid, "images": images[:1]},
        {**valid, "release_sha": "c" * 40},
        {**valid, "images": [{**item, "source_commit": "unknown"} for item in images]},
    ):
        with pytest.raises(ValueError):
            gate.qualify_zlib(invalid, "a" * 40)
    report = brace_match(name="zlib", version="1.3.2-r0", id="CVE-2026-85091")
    assert gate.review(report)["blockers"]
    assert gate.review(report, patched_zlib=True)["reviewed"]
    for change in ({"version": "1.3.1-r0"}, {"id": "CVE-OTHER"}, {"severity": "Critical"}):
        fields = {"name": "zlib", "version": "1.3.2-r0", "id": "CVE-2026-85091", **change}
        assert gate.review(brace_match(**fields), patched_zlib=True)["blockers"]
