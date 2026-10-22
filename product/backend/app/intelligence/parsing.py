"""Bounded, inert parsing. Document text never becomes executable instructions."""

import csv
import posixpath
import re
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from defusedxml import ElementTree as ET
from defusedxml.common import DefusedXmlException

from app.intelligence.passive_pdf import passive_reader
from app.intelligence.schema import Limits, ParsedDocument, ProcessingError, Source

NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


class Collector:
    def __init__(self, limits: Limits):
        self.limits = limits
        self.sources: list[Source] = []
        self.characters = 0
        self.cells = 0
        self.rows = 0
        self.warnings: set[str] = set()

    def add(self, label, raw, location, group=None):
        self.cells += 1
        self.characters += len(raw) + len(label)
        if self.cells > self.limits.max_cells or self.characters > self.limits.max_characters:
            raise ProcessingError("processing_limit")
        if raw.strip():
            self.sources.append(
                Source(id=len(self.sources), raw=raw, label=label, location=location, group=group)
            )

    def table(self, rows, location):
        header = None
        key_value = False
        for number, values in rows:
            self.rows += 1
            if self.rows > self.limits.max_rows:
                raise ProcessingError("processing_limit")
            if not any(str(value).strip() for value in values):
                continue
            if header is None:
                header = [value.strip() for value in values]
                if len(set(header)) != len(header) or any(not label for label in header):
                    raise ProcessingError("unsupported_structure")
                key_value = [h.lower() for h in header] in (["field", "value"], ["label", "value"])
                continue
            if len(values) != len(header):
                raise ProcessingError("unsupported_structure")
            for index, raw in enumerate(values):
                if key_value and index == 0:
                    continue
                label = values[0] if key_value else header[index]
                column = index + 1
                loc = {**location, "row": number, "column": column, "header": header[index]}
                if location["format"] == "pdf":
                    loc["line"] = number
                if location["format"] == "xlsx":
                    loc["cell"] = f"{column_name(column)}{number}"
                self.add(label, raw, loc, None if key_value else self.rows)

    def result(self):
        return ParsedDocument(sources=self.sources, warnings=sorted(self.warnings))


def column_name(number):
    name = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        name = chr(65 + remainder) + name
    return name


def parse_csv(path: Path, limits: Limits):
    collector = Collector(limits)
    csv.field_size_limit(limits.max_characters)
    try:
        with path.open(encoding="utf-8-sig", newline="") as stream:
            collector.table(enumerate(csv.reader(stream, strict=True), 1), {"format": "csv"})
    except (UnicodeError, csv.Error) as exc:
        code = (
            "processing_limit"
            if isinstance(exc, csv.Error) and "field larger than field limit" in str(exc)
            else "corrupt_document"
        )
        raise ProcessingError(code) from exc
    return collector.result()


def parse_xlsx(path: Path, limits: Limits):
    collector = Collector(limits)
    try:
        with ZipFile(path) as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            if (
                len(infos) > 1000
                or len(set(names)) != len(names)
                or sum(info.file_size for info in infos) > limits.max_zip_bytes
            ):
                raise ProcessingError("processing_limit")
            if any(
                "vbaproject" in name.lower() or name.startswith("/") or ".." in name.split("/")
                for name in names
            ):
                raise ProcessingError("unsupported_structure")

            def xml(name):
                return ET.fromstring(archive.read(name))

            strings = []
            if "xl/sharedStrings.xml" in names:
                for entry in xml("xl/sharedStrings.xml").findall("s:si", NS):
                    strings.append("".join(t.text or "" for t in entry.findall(".//s:t", NS)))
                if sum(map(len, strings)) > limits.max_characters:
                    raise ProcessingError("processing_limit")
            relationships = {}
            for relationship in xml("xl/_rels/workbook.xml.rels"):
                if relationship.get("TargetMode") == "External":
                    raise ProcessingError("unsupported_structure")
                target = relationship.get("Target", "")
                resolved = posixpath.normpath(posixpath.join("xl", target))
                if target.startswith("/xl/"):
                    resolved = target[1:]
                if not resolved.startswith("xl/worksheets/") or "\\" in resolved:
                    # Non-worksheet workbook relationships (styles, shared strings) are inert.
                    continue
                relationships[relationship.get("Id")] = resolved
            workbook = xml("xl/workbook.xml")
            for sheet in workbook.findall("s:sheets/s:sheet", NS):
                relation = sheet.get(
                    "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
                )
                if relation not in relationships:
                    raise ProcessingError("unsupported_structure")
                rows = []
                for row in xml(relationships[relation]).findall("s:sheetData/s:row", NS):
                    row_number = int(row.attrib["r"])
                    if row_number < 1 or row_number > limits.max_rows:
                        raise ProcessingError("processing_limit")
                    cells = {}
                    for cell in row.findall("s:c", NS):
                        reference = cell.attrib.get("r", "")
                        match = re.fullmatch(r"([A-Z]{1,3})([1-9][0-9]*)", reference)
                        if not match or int(match[2]) != row_number:
                            raise ProcessingError("unsupported_structure")
                        column = 0
                        for letter in match[1]:
                            column = column * 26 + ord(letter) - 64
                        if column > min(limits.max_cells, 1024) or column in cells:
                            raise ProcessingError("processing_limit")
                        if cell.find("s:f", NS) is not None:
                            collector.warnings.add("spreadsheet_formulas_ignored")
                            raw = ""
                        elif cell.get("t") == "s":
                            index = int(cell.findtext("s:v", default="-1", namespaces=NS))
                            if index < 0 or index >= len(strings):
                                raise ProcessingError("corrupt_document")
                            raw = strings[index]
                        elif cell.get("t") == "inlineStr":
                            raw = "".join(t.text or "" for t in cell.findall(".//s:t", NS))
                        else:
                            # Numeric/date serials stay exact XML strings. No float conversion.
                            raw = cell.findtext("s:v", default="", namespaces=NS)
                        cells[column] = raw
                    if cells:
                        rows.append(
                            (row_number, [cells.get(i, "") for i in range(1, max(cells) + 1)])
                        )
                    if len(rows) > limits.max_rows:
                        raise ProcessingError("processing_limit")
                # Excel omits trailing blank cells; extend to header width without inventing values.
                if rows:
                    width = len(rows[0][1])
                    rows = [(n, values + [""] * max(0, width - len(values))) for n, values in rows]
                collector.table(rows, {"format": "xlsx", "sheet": sheet.get("name", "")})
    except (BadZipFile, KeyError, ValueError, ET.ParseError, DefusedXmlException) as exc:
        raise ProcessingError("corrupt_document") from exc
    return collector.result()


def has_pdf_images(resources):
    """Find raster images inside nested Form XObjects without following cycles."""
    pending = [resources]
    visited = set()
    while pending:
        resources = pending.pop()
        resources = resources.get_object() if hasattr(resources, "get_object") else resources
        if id(resources) in visited:
            continue
        visited.add(id(resources))
        if len(visited) > 1000:
            raise ProcessingError("processing_limit")
        objects = resources.get("/XObject", {})
        objects = objects.get_object() if hasattr(objects, "get_object") else objects
        for reference in objects.values():
            obj = reference.get_object()
            if obj.get("/Subtype") == "/Image":
                return True
            if obj.get("/Subtype") == "/Form":
                pending.append(obj.get("/Resources", {}))
    return False


def parse_pdf(path: Path, limits: Limits):
    collector = Collector(limits)
    try:
        reader = passive_reader(path, limits.max_pages)
        needs_ocr = False
        for number, page in enumerate(reader.pages, 1):
            text = page.extract_text() or ""
            if len(text) > limits.max_characters:
                raise ProcessingError("processing_limit")
            images = has_pdf_images(page.get("/Resources", {}))
            if images:
                collector.warnings.add("image_content_not_interpreted")
            if images and len(re.sub(r"\s", "", text)) < limits.scanned_text_threshold:
                needs_ocr = True
            offset = 0
            table_rows = []
            for line_number, line in enumerate(text.splitlines(keepends=True), 1):
                line_length = len(line)
                line = line.rstrip("\r\n")
                if "|" in line:
                    table_rows.append(
                        (line_number, [v.strip() for v in line.strip("|").split("|")])
                    )
                else:
                    if table_rows:
                        collector.table(table_rows, {"format": "pdf", "page": number})
                        table_rows = []
                    label, separator, value = line.partition(":")
                    collector.add(
                        label if separator else "",
                        value.strip() if separator else line,
                        {
                            "format": "pdf",
                            "page": number,
                            "line": line_number,
                            "start": offset,
                            "end": offset + len(line),
                            "text": line,
                        },
                    )
                offset += line_length
            if table_rows:
                collector.table(table_rows, {"format": "pdf", "page": number})
        result = collector.result()
        result.needs_ocr = needs_ocr
        if needs_ocr:
            result.warnings.append("image_pages_need_ocr")
        return result
    except ProcessingError:
        raise
    except Exception as exc:
        raise ProcessingError("corrupt_document") from exc


def parse(path: Path, mime_type: str, limits: Limits) -> ParsedDocument:
    parser = {
        "application/pdf": parse_pdf,
        "text/csv": parse_csv,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": parse_xlsx,
    }.get(mime_type)
    if parser is None:
        raise ProcessingError("unsupported_structure")
    result = parser(path, limits)
    if not result.sources and not result.needs_ocr:
        raise ProcessingError("empty_document")
    return result
