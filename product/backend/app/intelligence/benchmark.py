"""Synthetic exact-match benchmark. This is not a real-world accuracy estimate."""

import json
import tempfile
from pathlib import Path

from app.intelligence.extraction import extract
from app.intelligence.parsing import parse
from app.intelligence.schema import REQUIRED, Limits


def flatten(structured):
    result = {}
    for section, values in structured.items():
        if isinstance(values, list):
            for index, entry in enumerate(values, 1):
                result.update({f"{section}.{index}.{key}": value for key, value in entry.items()})
        else:
            result.update({f"{section}.{key}": value for key, value in values.items()})
    return result


def evaluate(cases, factory):
    counts = dict(
        required_correct=0,
        required_total=0,
        missing_fabricated=0,
        missing_total=0,
        pricing_correct=0,
        pricing_total=0,
        lines_correct=0,
        lines_total=0,
        evidence_correct=0,
        evidence_total=0,
    )
    failures = []
    with tempfile.TemporaryDirectory() as directory:
        for case in cases:
            data, mime = factory(case)
            file = Path(directory) / "synthetic"
            file.write_bytes(data)
            parsed = parse(file, mime, Limits())
            result = extract(parsed, case["document_type"], Limits())
            values = flatten(result.structured)
            expected = case["expected"]
            if result.status != case["status"]:
                failures.append(f"{case['name']}:status")
            for path, truth in expected.items():
                if values.get(path) != truth:
                    failures.append(f"{case['name']}:{path}")
            for path in REQUIRED[case["document_type"]]:
                counts["required_total"] += 1
                counts["required_correct"] += values.get(path) == expected.get(path)
            # Every source-absent scalar stays null, including unsupported text.
            evidenced = {fact.path for fact in result.fields}
            absent = {path for path in values if path not in evidenced}
            for path in absent | {path for path, truth in expected.items() if truth is None}:
                counts["missing_total"] += 1
                counts["missing_fabricated"] += values.get(path) is not None
            collection = "lines" if case["document_type"] == "invoice" else "pricing"
            metric = "lines" if case["document_type"] == "invoice" else "pricing"
            counts[metric + "_total"] += 1
            line_keys = {key for key in expected if key.startswith(collection + ".")}
            correct = len(result.structured[collection]) == case["count"] and all(
                values.get(key) == expected[key] for key in line_keys
            )
            counts[metric + "_correct"] += correct
            if not correct:
                failures.append(f"{case['name']}:line_items")
            for fact in result.fields:
                counts["evidence_total"] += 1
                source = next((s for s in parsed.sources if s.id == fact.source["source_id"]), None)
                correct = (
                    source is not None
                    and source.raw == fact.raw_value
                    and all(fact.source.get(k) == v for k, v in source.location.items())
                )
                # Independent fixture location assertions also check actual cells and pages.
                if case["format"] == "pdf":
                    correct = correct and fact.source.get("page") == 1
                    if "text" in fact.source:
                        correct = correct and fact.raw_value in fact.source["text"]
                else:
                    row, column = fact.source["row"], fact.source["column"]
                    correct = correct and case["rows"][row - 1][column - 1] == fact.raw_value
                    if case["format"] == "xlsx":
                        correct = correct and fact.source.get("sheet") == "Synthetic"
                counts["evidence_correct"] += bool(correct)
                if not correct:
                    failures.append(f"{case['name']}:evidence:{fact.path}")
    return {
        "benchmark": "synthetic-explicit-labels-v1",
        "documents": len(cases),
        **counts,
        "required_field_exact_accuracy": counts["required_correct"]
        / max(1, counts["required_total"]),
        "missing_field_false_fabrication_rate": counts["missing_fabricated"]
        / max(1, counts["missing_total"]),
        "line_item_correctness": counts["lines_correct"] / max(1, counts["lines_total"]),
        "pricing_correctness": counts["pricing_correct"] / max(1, counts["pricing_total"]),
        "evidence_correctness": counts["evidence_correct"] / max(1, counts["evidence_total"]),
        "failures": failures,
        "limitation": "Synthetic labeled templates only; no claim about unseen real documents.",
    }


def main():
    from tests.intelligence_fixtures import fixture_bytes

    path = Path(__file__).resolve().parents[2] / "tests/fixtures/document_intelligence/golden.json"
    report = evaluate(json.loads(path.read_text()), fixture_bytes)
    print(json.dumps(report, indent=2))
    raise SystemExit(bool(report["failures"] or report["missing_fabricated"]))


if __name__ == "__main__":
    main()
