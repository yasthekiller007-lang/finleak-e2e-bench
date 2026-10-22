from typing import Protocol
from uuid import UUID

from pydantic import BaseModel

from app.domain.money import Money
from app.domain.tenancy import OrganizationContext
from app.modules.evidence import EvidenceDraft


class LeakageCandidate(BaseModel):
    category: str
    potential_exposure: Money
    explanation: str
    evidence: list[EvidenceDraft]


class LeakageRule(Protocol):
    code: str

    def evaluate(
        self, context: OrganizationContext, invoice_id: UUID, contract_version_id: UUID
    ) -> list[LeakageCandidate]: ...
