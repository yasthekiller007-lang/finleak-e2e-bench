"""Provider proposals contain source IDs, never trusted normalized financial values."""

import re
from collections import defaultdict

from app.intelligence.normalization import normalize
from app.intelligence.schema import (
    CONTRACT,
    EXTRACTOR_VERSION,
    INVOICE,
    LINE,
    PRICING,
    REQUIRED,
    ExtractionProvider,
    ExtractionResult,
    Fact,
    Limits,
    ParsedDocument,
    ProcessingError,
    Proposal,
)

ALIASES = {
    "contract number": "identity.contract_number",
    "agreement id": "identity.contract_number",
    "contract title": "identity.title",
    "supplier": "identity.supplier",
    "vendor": "identity.supplier",
    "supplier name": "identity.supplier",
    "customer": "identity.customer",
    "buyer": "identity.customer",
    "effective date": "dates.effective_date",
    "start date": "dates.effective_date",
    "expiration date": "dates.end_date",
    "end date": "dates.end_date",
    "execution date": "dates.signature_date",
    "signature date": "dates.signature_date",
    "currency": "currency.code",
    "contract currency": "currency.code",
    "invoice currency": "currency.code",
    "document kind": "identity.document_kind",
    "parent contract": "identity.parent_contract_reference",
    "amendment number": "identity.amendment_number",
    "changed terms": "identity.changed_terms",
    "referenced section": "identity.referenced_section",
    "payment terms": "payment.terms",
    "fixed fee": "commercial.fixed_fee",
    "recurring fee": "commercial.recurring_fee",
    "one time fee": "commercial.one_time_fee",
    "minimum commitment": "commercial.minimum_commitment",
    "maximum commitment": "commercial.maximum_commitment",
    "discount percentage": "discounts.percentage",
    "discount amount": "discounts.amount",
    "volume discount": "discounts.volume_terms",
    "rebate percentage": "rebates.percentage",
    "rebate amount": "rebates.amount",
    "credit conditions": "rebates.credit_conditions",
    "service credits": "rebates.service_credits",
    "sla credits": "rebates.sla_credits",
    "escalation clause": "price_changes.escalation_clause",
    "maximum increase": "price_changes.maximum_increase",
    "auto renewal": "renewal.auto_renewal",
    "renewal period": "renewal.period",
    "notice requirements": "renewal.notice_requirements",
    "invoice number": "identity.invoice_number",
    "invoice date": "dates.invoice_date",
    "due date": "dates.due_date",
    "subtotal": "totals.subtotal",
    "discount": "totals.discount",
    "tax": "totals.tax",
    "fees": "totals.fees",
    "credits": "totals.credits",
    "total": "totals.total",
    "total amount": "totals.total",
    "amount due": "totals.amount_due",
    "purchase order": "references.purchase_order",
    "po number": "references.purchase_order",
    "account number": "references.account_number",
    "billing entity": "identity.billing_entity",
}
LINE_ALIASES = {key.replace("_", " "): key for key in LINE}
LINE_ALIASES.update({"item code": "sku", "unit of measure": "unit", "line total": "total"})
PRICING_ALIASES = {key.replace("_", " "): key for key in PRICING}
PRICING_ALIASES.update(
    {
        "product name": "product",
        "service name": "product",
        "unit of measure": "unit",
        "threshold quantity": "threshold_quantity",
        "pricing tier": "tier",
    }
)


def schema(document_type):
    return (
        CONTRACT if document_type == "contract" else INVOICE if document_type == "invoice" else {}
    )


def field_type(path, document_type):
    parts = path.split(".")
    if len(parts) == 3 and parts[0] == ("pricing" if document_type == "contract" else "lines"):
        if not parts[1].isdigit() or not 1 <= int(parts[1]) <= 5000:
            return None
        return (PRICING if document_type == "contract" else LINE).get(parts[2])
    if len(parts) == 2:
        return schema(document_type).get(parts[0], {}).get(parts[1])
    return None


class ExplicitLabelProvider:
    identifier = "deterministic-explicit-labels"
    version = EXTRACTOR_VERSION

    def propose(self, parsed: ParsedDocument, document_type: str) -> list[Proposal]:
        if not schema(document_type):
            return []
        proposals = []
        groups = {}
        for source in parsed.sources:
            label = re.sub(r"[-_\s]+", " ", source.label.strip().lower())
            path = source.label.strip().lower()
            # Explicit schema paths and numbered line/pricing labels are supported.
            if field_type(path, document_type):
                proposals.append(Proposal(path, source.id))
                continue
            match = re.fullmatch(r"(line|pricing) ([1-9][0-9]*) (.+)", label)
            if match:
                collection = "lines" if match[1] == "line" else "pricing"
                keys = LINE_ALIASES if collection == "lines" else PRICING_ALIASES
                if match[3] in keys:
                    path = f"{collection}.{match[2]}.{keys[match[3]]}"
                    if field_type(path, document_type):
                        proposals.append(Proposal(path, source.id))
                continue
            keys = PRICING_ALIASES if document_type == "contract" else LINE_ALIASES
            if source.group is not None and label in keys:
                group = groups.setdefault(source.group, len(groups) + 1)
                collection = "pricing" if document_type == "contract" else "lines"
                proposals.append(Proposal(f"{collection}.{group}.{keys[label]}", source.id))
                continue
            path = ALIASES.get(label)
            # Also accept schema's canonical human-readable labels if unambiguous.
            if path is None:
                matches = [
                    f"{section}.{key}"
                    for section, fields in schema(document_type).items()
                    for key in fields
                    if key.replace("_", " ") == label
                ]
                path = matches[0] if len(matches) == 1 else None
            if document_type == "invoice" and label == "contract number":
                path = "references.contract_number"
            if document_type == "contract" and label == "account number":
                path = "identity.account_number"
            if path and field_type(path, document_type):
                proposals.append(Proposal(path, source.id))
        return proposals


def extract(
    parsed: ParsedDocument,
    document_type: str,
    limits: Limits,
    provider: ExtractionProvider | None = None,
) -> ExtractionResult:
    provider = provider or ExplicitLabelProvider()
    structured = {
        section: dict.fromkeys(fields) for section, fields in schema(document_type).items()
    }
    collection = "pricing" if document_type == "contract" else "lines"
    structured[collection] = []
    warnings = list(parsed.warnings)
    if not schema(document_type):
        warnings.append("secondary_document_extraction_deferred")
    proposals = provider.propose(parsed, document_type)
    if len(proposals) > limits.max_fields:
        raise ProcessingError("processing_limit")
    sources = {source.id: source for source in parsed.sources}
    grouped = defaultdict(list)
    for proposal in proposals:
        kind = field_type(proposal.path, document_type)
        source = sources.get(proposal.source_id)
        if not kind or source is None or not source.raw.strip():
            raise ProcessingError("schema_validation")
        value = normalize(source.raw, kind)
        if proposal.path == "payment.terms" and not re.fullmatch(
            r"(?:net [1-9][0-9]{0,2}(?: days)?|due upon receipt|payable upon receipt)",
            source.raw.strip(),
            re.IGNORECASE,
        ):
            value = None
        if proposal.path == "identity.document_kind":
            value = source.raw.strip().lower()
            if value not in {
                "original",
                "master agreement",
                "amendment",
                "addendum",
                "schedule",
                "pricing appendix",
            }:
                value = None
        grouped[proposal.path].append((source, kind, value))
    numbered = {int(path.split(".")[1]) for path in grouped if path.startswith(collection + ".")}
    if numbered and numbered != set(range(1, max(numbered) + 1)):
        raise ProcessingError("unsupported_structure")  # Do not invent line items for gaps.
    facts = []
    for path, candidates in sorted(grouped.items()):
        values = {value for _, _, value in candidates}
        conflict = len(values) != 1
        value = None if conflict else candidates[0][2]
        if conflict:
            warnings.append(f"conflicting_values:{path}")
        elif value is None:
            warnings.append(f"ambiguous_value:{path}")
        for source, kind, _ in candidates:
            facts.append(
                Fact(
                    path=path,
                    raw_value=source.raw,
                    normalized_value=value,
                    value_type=kind,
                    confidence="low" if value is None else "high",
                    reason="conflicting_sources"
                    if conflict
                    else "ambiguous_or_unsupported"
                    if value is None
                    else "explicit_label_exact_normalization",
                    source={**source.location, "source_id": source.id},
                )
            )
        parts = path.split(".")
        if len(parts) == 2:
            structured[parts[0]][parts[1]] = value
        else:
            number = int(parts[1])
            definition = PRICING if document_type == "contract" else LINE
            while len(structured[collection]) < number:
                structured[collection].append(dict.fromkeys(definition))
            structured[collection][number - 1][parts[2]] = value
    # Unrecognized nonempty material may contain facts this conservative provider missed.
    proposed_ids = {proposal.source_id for proposal in proposals}
    if any(source.id not in proposed_ids for source in parsed.sources):
        warnings.append("unrecognized_content_requires_review")
    for path in REQUIRED.get(document_type, ()):
        section, key = path.split(".")
        if structured[section][key] is None:
            warnings.append(f"missing_required:{path}")
    if document_type == "invoice" and not structured[collection]:
        warnings.append("line_items_missing")
    # Incomplete lines are retained, never silently completed or discarded.
    for index, line in enumerate(structured[collection], 1):
        required = (
            ("description", "quantity", "unit_price", "total")
            if collection == "lines"
            else ("unit_price",)
        )
        if any(line[key] is None for key in required):
            warnings.append(f"incomplete_{collection}:{index}")
    status = "needs_ocr" if parsed.needs_ocr else "needs_review" if warnings else "processed"
    return ExtractionResult(
        status=status,
        structured=structured,
        fields=facts,
        warnings=sorted(set(warnings)),
        provider=provider.identifier,
        extractor_version=provider.version,
    )
