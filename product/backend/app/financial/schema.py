"""Versioned reviewed financial meanings, never extraction authority."""

from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints, model_validator

from app.domain.money import Amount, Currency

Key = Annotated[str, StringConstraints(min_length=1, max_length=120)]


class Frozen(BaseModel):
    model_config = {"extra": "forbid", "frozen": True}


class Evidence(Frozen):
    document_id: UUID
    location: Annotated[str, StringConstraints(min_length=1, max_length=1000)]
    quote: Annotated[str, StringConstraints(min_length=1, max_length=10000)]
    field_id: UUID | None = None
    # Manual source review is explicit; not a source-free override.
    manual: bool = False
    supports: tuple[str, ...] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def grounded(self):
        if (self.field_id is None) != self.manual:
            raise ValueError("Use an extracted field or explicitly identify manual source review")
        return self


class Rounding(Frozen):
    quantum: Amount
    modes: tuple[
        Literal[
            "ROUND_HALF_UP",
            "ROUND_HALF_EVEN",
            "ROUND_HALF_DOWN",
            "ROUND_UP",
            "ROUND_DOWN",
            "ROUND_CEILING",
            "ROUND_FLOOR",
            "ROUND_05UP",
        ],
        ...,
    ]
    stage: Literal["scope", "component", "unknown"]
    alternatives_complete: bool
    justification: str = Field(min_length=1, max_length=2000)
    metadata_version: Key

    @model_validator(mode="after")
    def valid_quantum(self):
        if self.quantum <= 0 or self.quantum.normalize().as_tuple().digits != (1,):
            raise ValueError("Quantum must be a positive decimal power of ten")
        if not self.modes or len(set(self.modes)) != len(self.modes):
            raise ValueError("Review at least one distinct plausible rounding mode")
        return self


class Term(Frozen):
    supplier_party: Key | None = None
    customer_party: Key | None = None
    key: Key
    scope: Key
    family: Literal["unit_price", "fixed_fee", "percentage_discount", "unsupported"]
    pricing_type: Key
    currency: Currency | None
    unit: Key | None = None
    rate: Amount | None = None
    percentage: Amount | None = None
    discount_base: Literal["line", "sku_set", "invoice_subtotal"] | None = None
    eligible_members: tuple[Key, ...] = ()
    unconditional: bool | None = None
    effective_from: date | None
    effective_to: date | None  # Exclusive end, explicitly reviewed semantics.
    open_ended: bool = False
    date_basis: Literal["service", "invoice", "event"] | None
    invoice_date_fallback: bool = False
    full_cycle: Key | None = None
    supersedes: tuple[Key, ...] = ()  # Term-specific, evidence-backed replacement only.
    retroactive: bool = False
    retroactive_applicability_approved: bool = False
    tax_basis: Literal["exclusive", "separable", "unknown"]
    rounding: Rounding | None
    unresolved: tuple[Key, ...] = ()


class Credit(Frozen):
    key: Key
    scope: Key | None
    amount: Amount
    classification: Literal["credit", "adjustment"]
    within_invoice: bool


class BaseComponent(Frozen):
    billed_gross: Amount | None = None
    billed_discount: Amount | None = None
    posted_amount: Amount | None = None
    key: Key
    contractual_gross: Amount
    eligible: bool


class BillingScope(Frozen):
    supplier_party: Key | None = None
    customer_party: Key | None = None
    key: Key
    label: str = Field(min_length=1, max_length=255)
    members: tuple[Key, ...] = Field(min_length=1, max_length=100)
    scope: Key
    currency: Currency | None
    unit: Key | None
    quantity: Amount | None
    billed_rate: Amount | None
    posted_amount: Amount | None
    billed_gross: Amount | None
    billed_discount: Amount | None
    tax_basis: Literal["exclusive", "separable", "unknown"]
    service_from: date | None
    service_to: date | None
    invoice_date: date | None
    event_date: date | None = None
    date_conflict: bool = False
    cycle: Key | None = None
    complete_cycle: bool | None = None
    base_components: tuple[BaseComponent, ...] = Field(default=(), max_length=100)
    base_complete: bool | None = None
    credits: tuple[Credit, ...] = Field(default=(), max_length=100)
    contract_references: tuple[Key, ...] = ()
    po_references: tuple[Key, ...] = ()
    unresolved: tuple[Key, ...] = ()
    allocation_parent: Key | None = None
    # Each allocated segment must have both its own quantity and posted amount.


class Reference(Frozen):
    contract_reference: Key | None = None
    po_reference: Key | None = None


class PacketDocument(Frozen):
    document_id: UUID
    role: Literal["master", "amendment", "schedule", "exhibit", "exception"]


class Packet(Frozen):
    documents: tuple[PacketDocument, ...] = Field(min_length=1, max_length=100)
    scopes: tuple[Key, ...] = Field(min_length=1, max_length=100)
    effective_from: date | None
    effective_to: date | None
    open_ended: bool = False
    known_missing: tuple[Key, ...]
    complete: bool
    attestation: str = Field(min_length=1, max_length=2000)
    unresolved: tuple[Key, ...] = ()

    @model_validator(mode="after")
    def bounded(self):
        if len({d.document_id for d in self.documents}) != len(self.documents):
            raise ValueError("Packet documents must be distinct")
        if sum(d.role == "master" for d in self.documents) != 1:
            raise ValueError("One governing master is required")
        return self


class Association(Frozen):
    contract_source_id: UUID
    method: Literal["exact_reference", "approved_po", "manual"]
    identifier: Key | None
    rationale: str = Field(min_length=1, max_length=2000)


class Review(Frozen):
    kind: Literal["term", "billing_scope", "reference", "packet", "association"]
    key: Key
    expected_revision: UUID | None
    state: Literal["prepared", "approved", "revoked"]
    reason: str = Field(min_length=1, max_length=2000)
    uncertainty_resolution: str = Field(min_length=1, max_length=2000)
    knowledge_cutoff: datetime
    value: Term | BillingScope | Reference | Packet | Association
    evidence: tuple[Evidence, ...] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def typed_meaning(self):
        expected = {
            "term": Term,
            "billing_scope": BillingScope,
            "reference": Reference,
            "packet": Packet,
            "association": Association,
        }[self.kind]
        if not isinstance(self.value, expected):
            raise ValueError("Value must have the reviewed semantic type")
        if self.kind in {"packet", "association", "reference"} and self.key != self.kind:
            raise ValueError("Singleton review must use its kind as key")
        if isinstance(self.value, (Term, BillingScope)) and self.key != self.value.key:
            raise ValueError("Stable fact key must match the value key")
        return self


class CreateSource(Frozen):
    document_id: UUID
    kind: Literal["contract", "invoice"]


class Evaluate(Frozen):
    scope_key: Key
    expected_revisions: tuple[UUID, ...] = Field(max_length=500)


class FindingDecision(Frozen):
    status: Literal["confirmed", "false_positive", "needs_review"]
    reason: str = Field(min_length=1, max_length=2000)
    expected_decision: UUID | None
