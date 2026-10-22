import csv
import io
import re
import unicodedata
import zipfile
from pathlib import PurePosixPath
from typing import BinaryIO
from urllib.parse import unquote

from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException
from fastapi import HTTPException

from app.intelligence.passive_pdf import passive_reader
from app.intelligence.schema import Limits, ProcessingError

MIME_TYPES = {
    ".pdf": "application/pdf",
    ".csv": "text/csv",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def safe_filename(filename: str | None) -> str:
    name = unicodedata.normalize("NFC", filename or "").strip()
    decoded = unquote(name)
    if (
        not name
        or len(name.encode("utf-8")) > 255
        or any(char in name for char in ("/", "\\"))
        or any(char in decoded for char in ("/", "\\"))
        or any(unicodedata.category(char).startswith("C") for char in decoded)
        or any(unicodedata.category(char).startswith("C") for char in name)
        or not PurePosixPath(name).stem.strip(". ")
    ):
        raise HTTPException(
            422, "Filename must be a safe basename without paths or control characters"
        )
    return name


def validate_file(
    source: BinaryIO,
    filename: str,
    mime_type: str | None,
    max_bytes: int,
    limits: Limits | None = None,
) -> str:
    limits = limits or Limits()
    extension = PurePosixPath(filename).suffix.lower()
    canonical = MIME_TYPES.get(extension)
    if canonical is None or mime_type != canonical:
        raise HTTPException(415, "Use a PDF, UTF-8 CSV, or XLSX with its matching MIME type")
    source.seek(0, io.SEEK_END)
    size = source.tell()
    if size < 1:
        raise HTTPException(422, "Empty files cannot be uploaded")
    if size > max_bytes:
        raise HTTPException(413, "File exceeds the maximum upload size")
    source.seek(0)
    try:
        if extension == ".pdf":
            if not re.match(rb"%PDF-(?:1\.[0-7]|2\.0)", source.read(16)):
                raise ValueError()
            source.seek(max(0, size - 1024))
            if b"%%EOF" not in source.read():
                raise ValueError()
            source.seek(0)
            passive_reader(source, limits.max_pages)
        elif extension == ".csv":
            text = source.read().decode("utf-8-sig")
            if any(ord(char) < 32 and char not in "\r\n\t" for char in text):
                raise ValueError()
            has_rows = False
            for row in csv.reader(io.StringIO(text), strict=True):
                has_rows = has_rows or bool(row)
            if not has_rows:
                raise ValueError()
        else:
            with zipfile.ZipFile(source) as archive:
                entries = archive.infolist()
                names = {entry.filename for entry in entries}
                required = {"[Content_Types].xml", "_rels/.rels", "xl/workbook.xml"}
                if (
                    not required <= names
                    or len(entries) > 1000
                    or len(names) != len(entries)
                    or sum(entry.file_size for entry in entries) > limits.max_zip_bytes
                    or any(
                        entry.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}
                        or entry.flag_bits & 1
                        or ".." in PurePosixPath(entry.filename).parts
                        or entry.filename.startswith("/")
                        or "\\" in entry.filename
                        or entry.filename.lower().endswith("vbaproject.bin")
                        for entry in entries
                    )
                ):
                    raise ValueError()
                for required_name in required:
                    if archive.getinfo(required_name).file_size > 1024 * 1024:
                        raise ValueError()
                types = ElementTree.fromstring(archive.read("[Content_Types].xml"))
                expected = (
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"
                )
                if not any(
                    item.attrib.get("PartName") == "/xl/workbook.xml"
                    and item.attrib.get("ContentType") == expected
                    for item in types
                ):
                    raise ValueError()
                ElementTree.fromstring(archive.read("xl/workbook.xml"))
                for entry in entries:
                    if entry.filename.endswith(".rels"):
                        relationships = ElementTree.fromstring(archive.read(entry))
                        if any(
                            item.attrib.get("TargetMode") == "External" for item in relationships
                        ):
                            raise ValueError()
                    if "externalLinks/" in entry.filename or "activeX/" in entry.filename:
                        raise ValueError()
    except (
        ValueError,
        ProcessingError,
        UnicodeError,
        csv.Error,
        zipfile.BadZipFile,
        KeyError,
        DefusedXmlException,
        ElementTree.ParseError,
    ) as exc:
        raise HTTPException(415, "File content does not match a supported format") from exc
    finally:
        source.seek(0)
    return canonical
