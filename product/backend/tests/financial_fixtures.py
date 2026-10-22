from datetime import date
from uuid import uuid4

from app.financial.schema import BillingScope, Packet, Rounding, Term

DAY = date(2026, 6, 15)
ROUNDING = Rounding(
    quantum="0.01",
    modes=("ROUND_HALF_UP",),
    stage="scope",
    alternatives_complete=True,
    justification="Explicit synthetic source profile",
    metadata_version="synthetic-usd/1",
)


def term(**changes):
    data = dict(
        supplier_party="supplier-A",
        customer_party="buyer-A",
        key="price",
        scope="SKU-A",
        family="unit_price",
        pricing_type="fixed_unit",
        currency="USD",
        unit="unit",
        rate="10",
        effective_from=date(2026, 1, 1),
        effective_to=None,
        open_ended=True,
        date_basis="service",
        tax_basis="exclusive",
        rounding=ROUNDING,
    )
    return Term(**(data | changes))


def bill(**changes):
    data = dict(
        supplier_party="supplier-A",
        customer_party="buyer-A",
        key="line-1",
        label="Approved billed line",
        members=("line-1",),
        scope="SKU-A",
        currency="USD",
        unit="unit",
        quantity="100",
        billed_rate="12",
        posted_amount="1200",
        billed_gross="1200",
        billed_discount="0",
        tax_basis="exclusive",
        service_from=DAY,
        service_to=None,
        invoice_date=DAY,
    )
    return BillingScope(**(data | changes))


def packet(**changes):
    data = dict(
        documents=({"document_id": uuid4(), "role": "master"},),
        scopes=("SKU-A",),
        effective_from=date(2026, 1, 1),
        effective_to=None,
        open_ended=True,
        known_missing=(),
        complete=True,
        attestation="Synthetic bounded governing packet reviewed",
    )
    return Packet(**(data | changes))
