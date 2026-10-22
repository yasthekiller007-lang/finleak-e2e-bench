"""Versioned candidate schema. These facts are not financial or legal rules."""

from dataclasses import dataclass
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "document-candidates/1"
EXTRACTOR_VERSION = "explicit-labels/1"
PARSER_VERSION = "safe-parser/2"

CONTRACT = {
    "identity": {
        k: "text"
        for k in (
            "contract_number",
            "title",
            "parties",
            "supplier",
            "customer",
            "legal_entities",
            "account_number",
            "vendor_id",
            "customer_id",
            "document_kind",
            "parent_contract_reference",
            "amendment_number",
            "changed_terms",
            "referenced_section",
        )
    },
    "dates": {
        k: "date"
        for k in (
            "signature_date",
            "effective_date",
            "end_date",
            "renewal_date",
            "notice_deadline",
            "termination_date",
        )
    },
    "currency": {"code": "currency"},
    "commercial": {
        k: "decimal"
        for k in (
            "fixed_fee",
            "recurring_fee",
            "one_time_fee",
            "minimum_commitment",
            "maximum_commitment",
        )
    },
    "discounts": {
        "percentage": "decimal",
        "amount": "decimal",
        "volume_terms": "text",
        "effective_date": "date",
    },
    "rebates": {
        "percentage": "decimal",
        "amount": "decimal",
        "credit_conditions": "text",
        "service_credits": "text",
        "sla_credits": "text",
    },
    "payment": {
        k: "text" for k in ("terms", "due_terms", "early_payment_discount", "late_payment_terms")
    },
    "price_changes": {
        "escalation_clause": "text",
        "maximum_increase": "decimal",
        "index_linked_increase": "text",
        "effective_date": "date",
    },
    "renewal": {"auto_renewal": "boolean", "period": "text", "notice_requirements": "text"},
    "references": {k: "text" for k in ("purchase_order", "schedules", "amendments")},
}
INVOICE = {
    "identity": {
        k: "text"
        for k in (
            "invoice_number",
            "supplier",
            "customer",
            "supplier_id",
            "customer_id",
            "billing_entity",
        )
    },
    "dates": {k: "date" for k in ("invoice_date", "due_date", "service_start", "service_end")},
    "references": {
        k: "text"
        for k in (
            "contract_number",
            "purchase_order",
            "account_number",
            "customer_reference",
            "vendor_reference",
        )
    },
    "currency": {"code": "currency"},
    "totals": {
        k: "decimal"
        for k in ("subtotal", "discount", "tax", "fees", "credits", "total", "amount_due")
    },
}
LINE = {
    "description": "text",
    "sku": "text",
    "quantity": "decimal",
    "unit": "text",
    "unit_price": "decimal",
    "discount": "decimal",
    "tax": "decimal",
    "fees": "decimal",
    "total": "decimal",
    "service_start": "date",
    "service_end": "date",
    "purchase_order": "text",
    "contract_reference": "text",
}
PRICING = {
    "product": "text",
    "sku": "text",
    "description": "text",
    "unit": "text",
    "quantity": "decimal",
    "unit_price": "decimal",
    "discount_percentage": "decimal",
    "discount_amount": "decimal",
    "threshold_quantity": "decimal",
    "tier": "text",
    "effective_date": "date",
    "end_date": "date",
}
REQUIRED = {
    "contract": (
        "identity.contract_number",
        "identity.supplier",
        "dates.effective_date",
        "currency.code",
    ),
    "invoice": (
        "identity.invoice_number",
        "identity.supplier",
        "dates.invoice_date",
        "currency.code",
        "totals.total",
    ),
}


class Limits(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scanned_text_threshold: int = Field(default=60, ge=1, le=1000)
    max_pages: int = Field(default=100, ge=1, le=1000)
    max_rows: int = Field(default=5000, ge=1, le=100000)
    max_cells: int = Field(default=50000, ge=1, le=1000000)
    max_characters: int = Field(default=500000, ge=1024, le=5000000)
    max_fields: int = Field(default=5000, ge=1, le=20000)
    max_zip_bytes: int = Field(default=50 * 1024 * 1024, ge=1024, le=200 * 1024 * 1024)
    timeout_seconds: int = Field(default=20, ge=1, le=120)
    memory_mb: int = Field(default=512, ge=128, le=2048)


class Source(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: int
    raw: str
    label: str
    group: int | None = None
    location: dict[str, str | int]


class ParsedDocument(BaseModel):
    sources: list[Source]
    warnings: list[str] = Field(default_factory=list)
    needs_ocr: bool = False


@dataclass(frozen=True)
class Proposal:
    path: str
    source_id: int


class ExtractionProvider(Protocol):
    identifier: str
    version: str

    def propose(self, parsed: ParsedDocument, document_type: str) -> list[Proposal]: ...


class Fact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str
    raw_value: str
    normalized_value: str | bool | None
    value_type: Literal["text", "decimal", "currency", "date", "boolean"]
    confidence: Literal["high", "medium", "low"]
    reason: str
    source: dict[str, str | int]


class ExtractionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["processed", "needs_review", "needs_ocr"]
    structured: dict
    fields: list[Fact]
    warnings: list[str]
    provider: str
    extractor_version: str
    parser_version: str = PARSER_VERSION
    schema_version: str = SCHEMA_VERSION


class ProcessingError(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


ERROR_MESSAGES = {
    "parser_confinement_unavailable": "Protected parsing is unavailable. Processing is blocked.",
    "corrupt_document": "The document could not be read safely.",
    "encrypted_pdf": "Password-protected PDFs cannot be processed.",
    "empty_document": "The document contains no usable content.",
    "unsupported_structure": "This structure is not supported by the current extractor.",
    "processing_limit": "The document exceeds a configured processing limit.",
    "processing_timeout": "Processing exceeded its time limit. You can retry.",
    "provider_unavailable": "The extraction provider is temporarily unavailable.",
    "schema_validation": "The proposed extraction failed validation.",
    "content_unavailable": "The original document is unavailable.",
    "content_integrity": "The stored document failed its integrity check.",
    "interrupted": "An earlier processing attempt was interrupted. You can retry.",
}
