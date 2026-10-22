import io
import zipfile

import pytest
from fastapi import HTTPException

from app.modules.upload_validation import safe_filename, validate_file
from tests.test_documents import xlsx


@pytest.mark.parametrize(
    "name", [None, "../file.pdf", r"C:\file.pdf", "\x00.csv", "\u202e.csv", "%0d.csv", "..."]
)
def test_unsafe_basename(name):
    with pytest.raises(HTTPException) as error:
        safe_filename(name)
    assert error.value.status_code == 422


def test_csv_validates_entire_file_including_trailing_malformed_row():
    with pytest.raises(HTTPException) as error:
        validate_file(io.BytesIO(b'first,row\n"unterminated'), "file.csv", "text/csv", 1024)
    assert error.value.status_code == 415


@pytest.mark.parametrize(
    "name,content",
    [
        ("../escape", b"x"),
        ("xl/vbaProject.bin", b"macro"),
        (
            "xl/workbook.xml",
            b'<!DOCTYPE x [<!ENTITY attack SYSTEM "file:///etc/passwd">]><x>&attack;</x>',
        ),
        ("[Content_Types].xml", b"<Types/>"),
    ],
)
def test_xlsx_rejects_traversal_macros_duplicate_parts_and_xml_entities(name, content):
    result = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(xlsx())) as original, zipfile.ZipFile(result, "w") as output:
        for entry in original.infolist():
            output.writestr(
                entry.filename, content if entry.filename == name else original.read(entry)
            )
        if name not in original.namelist():
            output.writestr(name, content)
    with pytest.raises(HTTPException) as error:
        validate_file(
            result,
            "file.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            4096,
        )
    assert error.value.status_code == 415


@pytest.mark.parametrize(
    "key", ["/OpenAction", "/AA", "/JS", "/XFA", "/EmbeddedFiles", "/RichMedia"]
)
def test_active_pdf_originals_are_rejected_without_transforming_bytes(key):
    from pypdf import PdfWriter
    from pypdf.generic import DictionaryObject, NameObject, TextStringObject

    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer._root_object[NameObject(key)] = DictionaryObject(
        {NameObject("/JS"): TextStringObject("synthetic")}
    )
    result = io.BytesIO()
    writer.write(result)
    original = result.getvalue()
    with pytest.raises(HTTPException) as error:
        validate_file(result, "file.pdf", "application/pdf", 4096)
    assert error.value.status_code == 415
    assert result.getvalue() == original and result.tell() == 0


@pytest.mark.parametrize("action", ["/URI", "/Launch", "/GoToR", "/SubmitForm"])
def test_external_pdf_action_is_rejected_in_indirect_nested_graph(action):
    from pypdf import PdfWriter
    from pypdf.generic import ArrayObject, DictionaryObject, NameObject

    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    annotated = writer._add_object(
        DictionaryObject(
            {NameObject("/A"): DictionaryObject({NameObject("/S"): NameObject(action)})}
        )
    )
    page[NameObject("/Annots")] = ArrayObject([annotated])
    result = io.BytesIO()
    writer.write(result)
    with pytest.raises(HTTPException) as error:
        validate_file(result, "file.pdf", "application/pdf", 4096)
    assert error.value.status_code == 415


def test_external_xlsx_relationship_is_rejected_before_download_or_processing():
    result = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(xlsx())) as original, zipfile.ZipFile(result, "w") as output:
        for entry in original.infolist():
            output.writestr(entry.filename, original.read(entry))
        output.writestr(
            "xl/worksheets/_rels/sheet1.xml.rels",
            '<Relationships><Relationship TargetMode="External" Target="https://outside.example.test/source"/></Relationships>',
        )
    with pytest.raises(HTTPException) as error:
        validate_file(
            result,
            "file.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            4096,
        )
    assert error.value.status_code == 415
