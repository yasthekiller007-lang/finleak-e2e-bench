"""Strict bounded commands; deferred financial capabilities have no writable fields."""

from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.domain.money import Amount, Currency

Text = Annotated[str, StringConstraints(strict=True, min_length=1, max_length=4000)]
Identity = Annotated[str, StringConstraints(strict=True, min_length=1, max_length=120)]
Positive = Annotated[Amount, Field(gt=0)]
Nonnegative = Annotated[Amount, Field(ge=0)]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)


class Limits(Strict):
    profile: Literal["recovery-operations/1"] = "recovery-operations/1"
    request_bytes: int = Field(default=1048576, ge=1)
    text_chars: int = Field(default=4000, ge=1, le=4000)
    documents: int = Field(default=50, ge=1)
    bindings: int = Field(default=500, ge=1)
    source_bytes: int = Field(default=104857600, ge=1)
    work_seconds: int = Field(default=25, ge=1, le=25)
    response_bytes: int = Field(default=10485760, ge=1)
    history_page: int = Field(default=100, ge=1, le=100)
    projection_records: int = Field(default=10000, ge=1)
    tenant_concurrency: int = Field(default=2, ge=1)
    actor_operations_per_minute: int = Field(default=10, ge=1)


class Moment(Strict):
    precision: Literal["DATE", "INSTANT", "LOCAL"]
    day: date | None = None
    timestamp: datetime | None = None
    timezone: Identity | None = None

    @model_validator(mode="after")
    def exact_precision(self):
        if self.precision == "DATE":
            if self.day is None or self.timestamp is not None:
                raise ValueError("Date-only evidence needs its original date")
        elif self.precision == "INSTANT":
            if self.timestamp is None or self.timestamp.tzinfo is None or self.day is not None:
                raise ValueError("Exact instant requires an evidenced offset")
        elif self.timestamp is None or self.timestamp.tzinfo is not None or self.day is not None:
            raise ValueError("Local evidence preserves its original local timestamp")
        return self


class Evidence(Strict):
    document_id: UUID
    locator: Text
    quotation: Text
    supports: Annotated[tuple[Text, ...], Field(min_length=1, max_length=500)]
    raw_fields: dict[Identity, Text]
    reviewed_fields: dict[Identity, Text]


class Instrument(Strict):
    kind: Literal["CASH", "CREDIT", "LIABILITY", "COST", "SETTLEMENT"]
    namespace: Identity
    issuer: Identity
    reference: Identity
    currency: Currency


class Party(Strict):
    kind: Literal["party"] = "party"
    previous_party_id: UUID | None = None
    supplier: Identity
    customer: Identity
    payer: Identity
    payee: Identity
    beneficiary: Identity
    valid_from: date
    valid_to: date | None = None
    relationship: Literal[
        "DIRECT", "AGENCY", "ASSIGNMENT", "CONTINUITY", "PROCESSOR", "INTERCOMPANY"
    ]
    discharge: Text


class Readiness(Strict):
    kind: Literal["readiness"] = "readiness"
    proof_id: UUID
    decision_id: UUID
    party_id: UUID
    pursuit: Positive
    quantum: Positive
    currency: Currency
    tax_basis: Literal["EXCLUSIVE"]
    scope: Text
    reconciliation: Literal["COMPLETE", "UNRESOLVED"]


class Components(Strict):
    principal: Nonnegative | None = None
    gross: Nonnegative | None = None
    tax: Nonnegative | None = None
    fees: Nonnegative | None = None
    withholding: Nonnegative | None = None
    net_cash: Nonnegative | None = None
    other: Nonnegative | None = None
    tax_basis: Literal["EXCLUSIVE", "INCLUSIVE", "UNKNOWN"]
    tax_recoverability: Literal["NOT_ASSESSED"] = "NOT_ASSESSED"
    reconciliation: Literal["COMPLETE", "UNRESOLVED"]

    @model_validator(mode="after")
    def reconciled_bridge(self):
        from decimal import localcontext

        with localcontext() as ctx:
            ctx.prec = 80
            if self.reconciliation == "COMPLETE" and self.principal is not None:
                if self.tax_basis == "UNKNOWN":
                    raise ValueError("Unknown tax basis cannot be complete")
                if self.tax_basis == "INCLUSIVE" and self.tax is None:
                    raise ValueError("Inclusive basis requires evidenced tax")
                if self.gross is not None:
                    if self.tax is None or self.other is None:
                        raise ValueError("Gross bridge needs explicit tax and other components")
                    if self.gross != self.principal + self.tax + self.other:
                        raise ValueError("Gross bridge disagrees")
                if self.net_cash is not None and self.gross is not None:
                    if self.fees is None or self.withholding is None:
                        raise ValueError("Cash bridge needs explicit deductions")
                    if self.gross != self.net_cash + self.fees + self.withholding:
                        raise ValueError("Cash bridge disagrees")
        return self


class InstrumentReview(Components):
    kind: Literal["instrument"] = "instrument"
    instrument_id: UUID
    previous_review_id: UUID | None = None
    economic: Moment
    payer: Identity
    payee: Identity
    beneficiary: Identity
    scope: Text
    related_cases: Annotated[tuple[UUID, ...], Field(max_length=50)] = ()
    origin: Literal["POST_FINDING_REMEDY", "PREEXISTING", "UNRESOLVED"]
    status: Literal["SETTLED", "ISSUED", "POSTED", "INCURRED", "AGREED", "UNRESOLVED"]


class Realization(Components):
    kind: Literal["realization"] = "realization"
    instrument_id: UUID
    instrument_review_id: UUID
    party_id: UUID
    readiness_id: UUID
    method: Literal["CASH", "APPLIED_CREDIT", "LIABILITY_REDUCTION"]
    economic: Moment
    amount: Positive
    currency: Currency
    quantum: Positive
    event_reference: Identity
    replaces_id: UUID | None = None
    payer: Identity
    payee: Identity
    beneficiary: Identity
    scope: Text
    completed: Literal[True]
    application_reference: Identity | None = None
    unpaid_original: bool | None = None
    liability_before: Nonnegative | None = None
    liability_after: Nonnegative | None = None
    discharge: Text


class Reversal(Strict):
    kind: Literal["reversal"] = "reversal"
    original_id: UUID
    amount: Positive
    reversal_type: Literal["ECONOMIC_RETURN", "DE_RECOGNITION"]
    economic: Moment
    event_reference: Identity
    restored_credit: Nonnegative | None = None
    cash_return: Nonnegative | None = None
    discharge: Text


class CreditState(Strict):
    kind: Literal["credit_state"] = "credit_state"
    instrument_id: UUID
    state: Literal["CANCELLED", "EXPIRED", "RESTORED", "RECONCILED"]
    amount: Nonnegative
    economic: Moment
    original_id: UUID | None = None
    reconciliation: Literal["COMPLETE", "UNRESOLVED"]


class Claim(Strict):
    kind: Literal["claim"] = "claim"
    state: Literal["DRAFT", "RECORDED_ACTION", "WITHDRAWN", "REPLACED"]
    principal: Nonnegative | None = None
    currency: Currency
    tax_basis: Literal["EXCLUSIVE", "UNKNOWN"]
    economic: Moment
    scope: Text
    action_reference: Identity


class Vendor(Strict):
    kind: Literal["vendor"] = "vendor"
    state: Literal["ACKNOWLEDGED", "PARTLY_DISPUTED", "DISPUTED", "UNRESOLVED"]
    acknowledged: Nonnegative | None = None
    disputed: Nonnegative | None = None
    agreed_gross: Nonnegative | None = None
    currency: Currency
    tax_basis: Literal["EXCLUSIVE", "UNKNOWN"]
    party_id: UUID
    economic: Moment
    scope: Text
    conditional: bool


class Cost(Strict):
    kind: Literal["cost"] = "cost"
    instrument_id: UUID
    state: Literal["INCURRED", "PAID", "REVERSED"]
    event_reference: Identity
    principal: Positive
    currency: Currency
    economic: Moment
    original_id: UUID | None = None
    directly_attributable: Literal[True]
    scope: Text


class Alias(Strict):
    kind: Literal["alias"] = "alias"
    instrument_id: UUID
    identity: Instrument


class Revoke(Strict):
    kind: Literal["party_revoked"] = "party_revoked"
    party_id: UUID


class Retire(Strict):
    kind: Literal["retire"] = "retire"
    successor_case_id: UUID
    proof_successor_id: UUID


Value = Annotated[
    Party
    | Readiness
    | InstrumentReview
    | Realization
    | Reversal
    | CreditState
    | Claim
    | Vendor
    | Cost
    | Alias
    | Revoke
    | Retire,
    Field(discriminator="kind"),
]


class Proposal(Strict):
    value: Value
    evidence: Annotated[tuple[Evidence, ...], Field(max_length=500)]
    expected_head: UUID | None
    reason: Text


class Approve(Strict):
    expected_head: UUID | None
    reason: Text
    decision: Literal["APPROVE", "REJECT", "WITHDRAW"] = "APPROVE"


class CreateCase(Strict):
    evaluation_id: UUID


class Lifecycle(Strict):
    state: Literal["OPEN", "SUSPENDED", "CLOSED"]
    closure_reason: (
        Literal[
            "PARTIAL_SETTLEMENT",
            "FULL_SETTLEMENT",
            "ECONOMICS",
            "RELATIONSHIP",
            "IMMATERIALITY",
            "INSUFFICIENT_EVIDENCE",
            "LIMITATION_CONCERN",
            "MANAGEMENT",
            "OPERATIONAL",
            "INVALID_BASIS",
        ]
        | None
    ) = None
    expected_head: UUID | None
    reason: Text


class Workflow(Strict):
    assignee_id: UUID | None = None
    priority: Literal["LOW", "NORMAL", "HIGH", "URGENT"] = "NORMAL"
    target_date: date | None = None
    follow_up_date: date | None = None
    next_action: Text | None = None
    escalation: Literal["NONE", "REQUESTED", "REVIEWING"] = "NONE"
    expected_head: UUID | None
    reason: Text


class Note(Strict):
    text: Text
    replaces_id: UUID | None = None
    retracted: bool = False
    expected_head: UUID | None
    reason: Text


class Report(Strict):
    known_at: datetime
    start: Moment
    end: Moment
    timezone: Identity | None = None
    currency: Currency
    customer: Identity
    tax_basis: Literal["EXCLUSIVE"]

    @model_validator(mode="after")
    def knowledge_offset(self):
        if self.known_at.tzinfo is None:
            raise ValueError("Knowledge cutoff requires exact offset")
        return self
