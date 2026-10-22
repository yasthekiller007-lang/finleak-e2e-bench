from datetime import date
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.money import Confidence, Money
from app.domain.tenancy import OrganizationContext
from app.modules.evidence import SourceReference


class ExtractedContract(BaseModel):
    document_id: UUID
    counterparty_name: str | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    agreed_amount: Money | None = None
    confidence: Confidence | None = None
    sources: list[SourceReference] = Field(default_factory=list)


class ContractExtractor(Protocol):
    """Document understanding produces candidates, never authoritative calculations."""

    def extract(self, context: OrganizationContext, document_id: UUID) -> ExtractedContract: ...
