from typing import Protocol
from uuid import UUID

from pydantic import BaseModel

from app.domain.money import Confidence
from app.domain.tenancy import OrganizationContext


class MatchCandidate(BaseModel):
    contract_id: UUID
    contract_version_id: UUID | None = None
    confidence: Confidence | None = None
    explanation: str


class ContractMatcher(Protocol):
    """Candidates must belong to context.organization_id; no fuzzy algorithm yet."""

    def match(self, context: OrganizationContext, invoice_id: UUID) -> list[MatchCandidate]: ...
