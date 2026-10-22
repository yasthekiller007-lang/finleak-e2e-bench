"""Strict wire validation layered on the existing exception Filters, not a query engine."""

import re
import unicodedata
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.financial.exceptions_query import Filters

MAX_REVISION = 9007199254740991
FLAGS = {"current", "needs_review", "missing_contract"}
IDS = {"contract_source_id", "invoice_source_id", "invoice_document_id"}
DATES = {"created_from", "created_to"}
UUID_TEXT = re.compile(r"^[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}$")
DATE_TEXT = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,3})?(?:Z|[+-]\d{2}:\d{2})$")


def safe_text(value):
    if not isinstance(value, str) or any(
        unicodedata.category(c) in {"Cc", "Cf", "Cs"} for c in value
    ):
        raise ValueError("Unsupported text")
    value.encode("utf-8", errors="strict")
    return value


def clean_name(value):
    value = " ".join(unicodedata.normalize("NFKC", safe_text(value)).split())
    if not 1 <= len(value) <= 80 or len(value.casefold()) > 240:
        raise ValueError("Use a name between 1 and 80 characters")
    return value


def normalized_name(value):
    return clean_name(value).casefold()


class SavedCriteria(Filters):
    model_config = ConfigDict(extra="forbid")
    outcome: Literal["POTENTIAL_LEAKAGE", "NEEDS_REVIEW", "NO_OVERCHARGE", "UNDERCHARGE"] | None = (
        None
    )

    @model_validator(mode="before")
    @classmethod
    def strict_wire(cls, value):
        if type(value) is not dict:
            raise ValueError("Criteria must be an object")
        for key, item in value.items():
            if key not in cls.model_fields:
                raise ValueError("Unknown criterion")
            if key in FLAGS:
                if type(item) is not bool:
                    raise ValueError("Flags must be booleans")
            else:
                safe_text(item)
                if key in IDS and not UUID_TEXT.fullmatch(item):
                    raise ValueError("Invalid source identity")
                if key in DATES and not DATE_TEXT.fullmatch(item):
                    raise ValueError("Use a timezone-aware creation date")
        return value


class Definition(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    view_type: Literal["anomalies", "review"]
    format_version: Literal[1] = 1
    criteria: SavedCriteria
    page_size: Literal[20, 50, 100] = 20

    @model_validator(mode="before")
    @classmethod
    def defaults(cls, value):
        if type(value) is dict:
            value = dict(value)
            if (
                type(value.get("format_version", 1)) is not int
                or type(value.get("page_size", 20)) is not int
            ):
                raise ValueError("Integer format and page size required")
            criteria = value.get("criteria")
            if type(criteria) is dict and "needs_review" not in criteria:
                value["criteria"] = {**criteria, "needs_review": value.get("view_type") == "review"}
        return value


class CreateView(Definition):
    name: str
    _name = field_validator("name", mode="before")(clean_name)


class UpdateView(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    expected_revision: int = Field(ge=1, le=MAX_REVISION)
    name: str | None = None
    definition: Definition | None = None

    @field_validator("name", mode="before")
    @classmethod
    def name_value(cls, value):
        return clean_name(value)

    @model_validator(mode="after")
    def nonempty(self):
        if len({"name", "definition"} & self.model_fields_set) != 1:
            raise ValueError("Choose either a rename or an explicit criteria update")
        if "definition" in self.model_fields_set and self.definition is None:
            raise ValueError("Definition cannot be null")
        return self


class DeleteView(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    expected_revision: int = Field(ge=1, le=MAX_REVISION)
