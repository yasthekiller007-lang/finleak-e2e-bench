"""Bounded PDF structure qualification; no rendering/actions or byte transformation."""

from pypdf import PdfReader
from pypdf.generic import ArrayObject, DictionaryObject, IndirectObject

from app.intelligence.schema import ProcessingError

# Passive financial originals only. Missing support is explicit, never repaired.
ACTIVE_KEYS = {
    "/OpenAction",
    "/AA",
    "/JS",
    "/JavaScript",
    "/XFA",
    "/EmbeddedFiles",
    "/EF",
    "/RichMedia",
    "/RichMediaContent",
    "/RichMediaSettings",
}
ACTIVE_ACTIONS = {
    "/JavaScript",
    "/Launch",
    "/URI",
    "/SubmitForm",
    "/ImportData",
    "/GoToR",
    "/GoToE",
    "/Sound",
    "/Movie",
    "/Rendition",
}


def passive_reader(source, max_pages=100):
    try:
        reader = PdfReader(source, strict=True)
        if reader.is_encrypted:
            raise ProcessingError("encrypted_pdf")
        if len(reader.pages) > max_pages:
            raise ProcessingError("processing_limit")
        pending, visited, count = [reader.trailer], set(), 0
        while pending:
            count += 1
            if count > 50000:
                raise ProcessingError("processing_limit")
            item = pending.pop()
            if isinstance(item, IndirectObject):
                key = (item.idnum, item.generation)
                if key in visited:
                    continue
                visited.add(key)
                item = item.get_object()
            if isinstance(item, DictionaryObject):
                if ACTIVE_KEYS.intersection(item) or item.get("/S") in ACTIVE_ACTIONS:
                    raise ProcessingError("unsupported_structure")
                pending.extend(item.values())
            elif isinstance(item, ArrayObject):
                pending.extend(item)
        return reader
    except ProcessingError:
        raise
    except Exception:
        raise ProcessingError("corrupt_document") from None
