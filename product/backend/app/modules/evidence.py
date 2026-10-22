from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.money import Money
from app.domain.tenancy import OrganizationContext


class SourceReference(BaseModel):
    document_id: UUID
    page_number: int | None = Field(default=None, ge=1)
    extracted_field: str | None = None
    source_text: str | None = None
    source_location: str | None = None


class CalculationTrace(BaseModel):
    reference: str
    expression: str
    inputs: dict[str, Money]
    result: Money


class EvidenceDraft(BaseModel):
    source: SourceReference
    calculation: CalculationTrace | None = None


class EvidenceGenerator(Protocol):
    def generate(
        self, context: OrganizationContext, sources: list[SourceReference], trace: CalculationTrace
    ) -> list[EvidenceDraft]: ...
