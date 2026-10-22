"""Read-only context from the frozen evaluation; no new financial policy or queries."""

from uuid import UUID


def queue_context(snapshot: dict, invoice_source_id: UUID) -> dict:
    bill = snapshot.get("billing_scope") or {}
    supplier = bill.get("supplier_party")
    references = bill.get("contract_references") or []
    contract_ids = set()
    for record in snapshot.get("inputs", []):
        if (
            record.get("kind") == "association"
            and record.get("state") == "approved"
            and record.get("source_id") == str(invoice_source_id)
        ):
            value = record.get("payload", {}).get("value", {}).get("contract_source_id")
            try:
                contract_ids.add(str(UUID(str(value))))
            except (ValueError, TypeError, AttributeError):
                continue
    return {
        "supplier_party": supplier if isinstance(supplier, str) and supplier else None,
        "contract_source_id": next(iter(contract_ids)) if len(contract_ids) == 1 else None,
        "contract_references": [r for r in references if isinstance(r, str)]
        if isinstance(references, list)
        else [],
    }
