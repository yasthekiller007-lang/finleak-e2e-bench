"""Synthetic files only. No real company documents or confidential data."""

import csv
import io
import zipfile
from xml.sax.saxutils import escape

from pypdf import PdfWriter
from pypdf.generic import (
    DecodedStreamObject,
    DictionaryObject,
    NameObject,
    NumberObject,
)


def pdf_bytes(text="", *, scanned=False, encrypted=False, pages=1):
    writer = PdfWriter()
    for _ in range(pages):
        page = writer.add_blank_page(width=612, height=792)
        font = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }
        )
        resources = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})}
        )
        if scanned:
            image = DecodedStreamObject()
            image.set_data(b"\xff\xff\xff")
            image.update(
                {
                    NameObject("/Type"): NameObject("/XObject"),
                    NameObject("/Subtype"): NameObject("/Image"),
                    NameObject("/Width"): NumberObject(1),
                    NameObject("/Height"): NumberObject(1),
                    NameObject("/ColorSpace"): NameObject("/DeviceRGB"),
                    NameObject("/BitsPerComponent"): NumberObject(8),
                }
            )
            resources[NameObject("/XObject")] = DictionaryObject(
                {NameObject("/Im1"): writer._add_object(image)}
            )
        page[NameObject("/Resources")] = resources
        stream = DecodedStreamObject()
        instructions = "BT /F1 10 Tf 40 750 Td "
        for line in text.splitlines():
            escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            instructions += f"({escaped}) Tj 0 -14 Td "
        instructions += "ET"
        if scanned:
            instructions += " q 10 0 0 10 0 0 cm /Im1 Do Q"
        stream.set_data(instructions.encode("ascii"))
        page[NameObject("/Contents")] = writer._add_object(stream)
    if encrypted:
        writer.encrypt("synthetic-password")
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def column_name(number):
    letters = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def xlsx_bytes(rows, *, formula=False):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            (
                '<Types xmlns="http://schemas.openxmlformats.org/package/2006/cont'
                'ent-types"><Override PartName="/xl/workbook.xml" ContentType="app'
                "lication/vnd.openxmlformats-officedocument.spreadsheetml.sheet.ma"
                'in+xml"/></Types>'
            ),
        )
        archive.writestr(
            "_rels/.rels",
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>',
        )
        archive.writestr(
            "xl/workbook.xml",
            (
                '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/'
                '2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocum'
                'ent/2006/relationships"><sheets><sheet name="Synthetic" sheetId="'
                '1" r:id="rId1"/></sheets></workbook>'
            ),
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            (
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2'
                '006/relationships"><Relationship Id="rId1" Type="http://schemas.o'
                'penxmlformats.org/officeDocument/2006/relationships/worksheet" Ta'
                'rget="worksheets/sheet1.xml"/></Relationships>'
            ),
        )
        content = '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
        for number, values in enumerate(rows, 1):
            content += f'<row r="{number}">'
            for index, value in enumerate(values, 1):
                reference = f"{column_name(index)}{number}"
                if formula and number == 2 and index == 2:
                    content += (
                        f'<c r="{reference}"><f>'
                        'HYPERLINK("https://attacker.invalid", "run")</f>'
                        "<v>999</v></c>"
                    )
                else:
                    content += (
                        f'<c r="{reference}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>'
                    )
            content += "</row>"
        archive.writestr("xl/worksheets/sheet1.xml", content + "</sheetData></worksheet>")
    return output.getvalue()


def fixture_bytes(case):
    if case["format"] == "pdf":
        return pdf_bytes(
            case.get("text", ""), scanned=case.get("scanned", False)
        ), "application/pdf"
    if case["format"] == "xlsx":
        return xlsx_bytes(
            case["rows"]
        ), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    stream = io.StringIO(newline="")
    csv.writer(stream).writerows(case["rows"])
    return stream.getvalue().encode(), "text/csv"
