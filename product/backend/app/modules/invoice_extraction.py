from datetime import date
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.money import Amount, Confidence, Money
from app.domain.tenancy import OrganizationContext
from app.modules.evidence import SourceReference


class ExtractedInvoiceLine(BaseModel):
    description: str
    quantity: Amount = Field(gt=0)
    unit_amount: Money
    line_amount: Money


class ExtractedInvoice(BaseModel):
    document_id: UUID
    invoice_number: str | None = None
    supplier_name: str | None = None
    issued_on: date | None = None
    total: Money | None = None
    lines: list[ExtractedInvoiceLine] = Field(default_factory=list)
    confidence: Confidence | None = None
    sources: list[SourceReference] = Field(default_factory=list)


class InvoiceExtractor(Protocol):
    def extract(self, context: OrganizationContext, document_id: UUID) -> ExtractedInvoice: ...
