from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class OperationalLimits(BaseModel):
    """Engineering defaults, not financial policy. Every operation records the profile."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    version: str = Field(default="proof-operations/1", min_length=1, max_length=80)
    request_bytes: int = Field(default=1024 * 1024, ge=1)
    annotation_characters: int = Field(default=4000, ge=1)
    revisions: int = Field(default=500, ge=1)
    documents: int = Field(default=100, ge=1)
    bindings: int = Field(default=5000, ge=1)
    canonical_bytes: int = Field(default=10 * 1024 * 1024, ge=1)
    source_bytes: int = Field(default=100 * 1024 * 1024, ge=1)
    work_seconds: int = Field(default=25, ge=1, le=25)
    history_page: int = Field(default=100, ge=1, le=100)
    tenant_concurrency: int = Field(default=2, ge=1, le=2)
    actor_operations_per_minute: int = Field(default=10, ge=1)


class Command(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Generate(Command):
    mode: Literal["CURRENT", "HISTORICAL"] = "CURRENT"
    expected_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    previous_package_id: UUID | None = None
    revision_reason: (
        Literal["REPAIRED_EVIDENCE", "SCHEMA_EVOLUTION", "ASSEMBLY_EVOLUTION"] | None
    ) = None

    @model_validator(mode="after")
    def explicit_revision(self):
        if (self.previous_package_id is None) != (self.revision_reason is None):
            raise ValueError("Content revisions need an explicit predecessor and reason")
        return self


class Event(Command):
    kind: Literal[
        "annotation.appended",
        "annotation.retracted",
        "review.proposed",
        "review.finalized",
        "disclosure.proposed",
        "disclosure.approved",
    ]
    text: str = Field(min_length=1, max_length=4000, pattern=r"^[^\x00]+$")
    previous_id: UUID | None = None
    status: Literal["REVIEWED", "NEEDS_REVIEW"] | None = None
    paths: list[str] = Field(default_factory=list, max_length=5000)

    @model_validator(mode="after")
    def fields_for_kind(self):
        if self.kind.startswith("review.") != (self.status is not None):
            raise ValueError("Review status is separate from technical completeness")
        if self.paths and self.kind != "disclosure.proposed":
            raise ValueError("Only disclosure proposals carry redaction paths")
        if self.kind in {"annotation.retracted", "disclosure.approved"} and not self.previous_id:
            raise ValueError("An attributed predecessor is required")
        return self


class Export(Command):
    disclosure_id: UUID | None = None


class Successor(Command):
    successor_id: UUID
    reason: str = Field(min_length=1, max_length=2000, pattern=r"^[^\x00]+$")
