from datetime import date
from decimal import Decimal, localcontext

import pytest
from pydantic import ValidationError

from app.financial.engine import evaluate, fingerprint
from app.financial.schema import BaseComponent, Credit
from tests.financial_fixtures import ROUNDING, bill, packet, term


def run(terms=None, billing=None, governing=None):
    return evaluate(tuple(terms or (term(),)), billing or bill(), governing or packet())


def fixed(rate="100"):
    return term(family="fixed_fee", pricing_type="fixed_cycle", rate=rate, full_cycle="monthly")


def fixed_bill(gross="150", **changes):
    return bill(
        **(
            dict(
                quantity=None,
                billed_rate=None,
                posted_amount=gross,
                billed_gross=gross,
                cycle="monthly",
                complete_cycle=True,
            )
            | changes
        )
    )


def discount(percent="8", **changes):
    return term(
        **(
            dict(
                key="discount",
                family="percentage_discount",
                pricing_type="unconditional_percentage",
                rate=None,
                percentage=percent,
                unconditional=True,
                discount_base="line",
            )
            | changes
        )
    )


def base_bill(base="50000", posted="50000", **changes):
    return bill(
        **(
            dict(
                quantity=None,
                billed_rate=None,
                billed_gross=base,
                posted_amount=posted,
                base_components=(
                    BaseComponent(key="line-1", contractual_gross=base, eligible=True),
                ),
                base_complete=True,
            )
            | changes
        )
    )


def credit(amount="-200", scope="line-1"):
    return Credit(
        key="credit", scope=scope, amount=amount, classification="credit", within_invoice=True
    )


def vectors():
    unsupported = term(family="unsupported", pricing_type="tiered")
    old = term(effective_to=date(2026, 7, 1))
    new = term(key="amendment", rate="12", effective_from=date(2026, 7, 1), supersedes=("price",))
    return [
        (
            "F01",
            (term(),),
            bill(billed_rate="10", billed_gross="1000", posted_amount="1000"),
            "NO_OVERCHARGE",
            "0",
        ),
        (
            "F02",
            (term(rate="18.40"),),
            bill(
                quantity="43647",
                billed_rate="20.10",
                billed_gross="877304.70",
                posted_amount="877304.70",
            ),
            "POTENTIAL_LEAKAGE",
            "74199.90",
        ),
        (
            "F03",
            (term(),),
            bill(billed_rate="9", billed_gross="900", posted_amount="900"),
            "UNDERCHARGE",
            "-100",
        ),
        ("F04", (discount(),), base_bill(), "POTENTIAL_LEAKAGE", "4000"),
        (
            "F05",
            (discount(),),
            base_bill(posted="46000", billed_discount="4000"),
            "NO_OVERCHARGE",
            "0",
        ),
        ("F06", (fixed("5000"),), fixed_bill("5400"), "POTENTIAL_LEAKAGE", "400"),
        ("F07", (fixed("250"),), fixed_bill("250"), "NO_OVERCHARGE", "0"),
        *[(f"F{i:02}", (unsupported,), bill(), "UNSUPPORTED_RULE", None) for i in (8, 9, 10, 11)],
        (
            "F12",
            (old, new),
            bill(
                service_from=date(2026, 7, 15),
                billed_rate="13",
                billed_gross="1300",
                posted_amount="1300",
            ),
            "POTENTIAL_LEAKAGE",
            "100",
        ),
        ("F13", (old, new), bill(invoice_date=date(2026, 8, 15)), "POTENTIAL_LEAKAGE", "200"),
        ("F14", (old, new), bill(service_to=date(2026, 7, 15)), "ALLOCATION_REQUIRED", None),
        ("F15", (term(),), bill(currency="EUR"), "CURRENCY_MISMATCH", None),
        (
            "F16",
            (term(rate="18.40"),),
            bill(quantity=None, billed_rate="20.10", billed_gross="2010", posted_amount="2010"),
            "QUANTITY_MISSING",
            None,
        ),
        ("F17", (term(), term(key="conflict", rate="12")), bill(), "AMBIGUOUS_CONTRACT", None),
        ("F18", (unsupported,), bill(posted_amount="-500"), "UNSUPPORTED_RULE", None),
        ("F19", (fixed(),), fixed_bill(credits=(credit("-50"),)), "NO_OVERCHARGE", "0"),
        # F20 exercises actual matching in the PostgreSQL service suite.
        ("F21", (term(),), bill(credits=(credit(),)), "NO_OVERCHARGE", "0"),
        *[
            (
                f"F{i:02}",
                (term(family="unsupported", pricing_type=kind),),
                bill(),
                "UNSUPPORTED_RULE",
                None,
            )
            for i, kind in [(22, "prohibited_fee"), (23, "percentage_surcharge")]
        ],
        (
            "F24",
            (term(rate="100"),),
            bill(
                quantity="1",
                billed_rate="100",
                billed_gross="100",
                posted_amount="100",
                tax_basis="separable",
            ),
            "NO_OVERCHARGE",
            "0",
        ),
        (
            "F25",
            (new.model_copy(update={"retroactive": True}),),
            bill(service_from=date(2026, 7, 15)),
            "RETROACTIVE_APPLICABILITY",
            None,
        ),
        (
            "F26",
            (
                term(
                    rate="10.005",
                    rounding=ROUNDING.model_copy(
                        update={"modes": ("ROUND_HALF_UP", "ROUND_HALF_EVEN")}
                    ),
                ),
            ),
            bill(quantity="1", billed_rate="10.01", billed_gross="10.01", posted_amount="10.01"),
            "ROUNDING_MATERIAL",
            None,
        ),
        ("F27", (term(), discount("10")), bill(), "POTENTIAL_LEAKAGE", "300"),
        (
            "F28",
            (
                term(
                    family="percentage_discount",
                    pricing_type="early_payment",
                    percentage="2",
                    unconditional=False,
                ),
            ),
            bill(),
            "UNSUPPORTED_RULE",
            None,
        ),
        ("F29", (old,), bill(service_from=date(2026, 7, 15)), "TERM_NOT_APPLICABLE", None),
        (
            "F30",
            (term(unit="box"),),
            bill(billed_rate="2", billed_gross="200", posted_amount="200"),
            "UNIT_MISMATCH",
            None,
        ),
        (
            "F31",
            (term(family="unsupported", pricing_type="minimum"),),
            bill(),
            "UNSUPPORTED_RULE",
            None,
        ),
        (
            "F32",
            (term(rate="18.4", effective_to=date(2026, 7, 1)),),
            bill(
                quantity="400",
                billed_rate="19.2",
                billed_gross="7680",
                posted_amount="7680",
                allocation_parent="split-1",
            ),
            "POTENTIAL_LEAKAGE",
            "320",
        ),
        (
            "F33",
            (discount("10", discount_base="sku_set", eligible_members=("A",)),),
            base_bill(
                "2300",
                posted="2300",
                members=("A", "fee"),
                base_components=(
                    BaseComponent(key="A", contractual_gross="2000", eligible=True),
                    BaseComponent(key="fee", contractual_gross="300", eligible=False),
                ),
            ),
            "POTENTIAL_LEAKAGE",
            "200",
        ),
        (
            "F34",
            (term(),),
            bill(billed_rate="10", billed_gross="1000", posted_amount="1100"),
            "ACTUAL_BILLING_CONFLICT",
            None,
        ),
        (
            "F35",
            (term(),),
            bill(quantity="150", billed_rate="10", billed_gross="1500", posted_amount="1500"),
            "NO_OVERCHARGE",
            "0",
        ),
    ]


@pytest.mark.parametrize("name,terms,billing,expected,delta", vectors())
def test_approved_financial_vectors(name, terms, billing, expected, delta):
    result = run(terms, billing)
    assert result.reason == expected, (name, result)
    if delta is None:
        assert result.potential is None and result.discrepancy is None
        assert result.expected is None and result.actual is None
    else:
        assert result.discrepancy == Decimal(delta)
        assert result.potential == (Decimal(delta) if Decimal(delta) > 0 else None)


def test_allocated_period_segments_are_independent_not_a_third_finding():
    first = run(
        (term(rate="18.4", effective_to=date(2026, 7, 1)),),
        bill(quantity="400", billed_rate="19.2", posted_amount="7680", billed_gross="7680"),
    )
    second = run(
        (term(rate="19.1", effective_from=date(2026, 7, 1)),),
        bill(
            key="line-2",
            members=("line-2",),
            service_from=date(2026, 7, 15),
            quantity="600",
            billed_rate="19.2",
            posted_amount="11520",
            billed_gross="11520",
        ),
    )
    assert first.potential + second.potential == Decimal("380")


@pytest.mark.parametrize("field", ["rate", "percentage"])
@pytest.mark.parametrize("value", [0.1, True, "Infinity", "NaN", "1.0000001", "100000000000000"])
def test_contractual_decimal_validation(field, value):
    with pytest.raises(ValidationError):
        term(**{field: value})


@pytest.mark.parametrize(
    "quantity,rate,actual",
    [("0.123456", "0.123456", "0.02"), ("1", "0.005", "0.01"), ("1", "0.015", "0.02")],
)
def test_exact_intermediates_and_explicit_rounding(quantity, rate, actual):
    result = run(
        (term(rate=rate),),
        bill(quantity=quantity, billed_rate=rate, billed_gross=None, posted_amount=actual),
    )
    assert result.expected == Decimal(actual)
    assert Decimal(result.trace["expected_raw"]) == Decimal(quantity) * Decimal(rate)


def test_rounding_context_is_independent_of_process_settings():
    with localcontext() as ambient:
        ambient.prec = 3
        result = run(
            (term(rate="18.4"),),
            bill(
                quantity="43647",
                billed_rate="20.1",
                posted_amount="877304.7",
                billed_gross="877304.7",
            ),
        )
    assert result.potential == Decimal("74199.90")


def test_complete_rounding_alternatives_are_invariant_for_aligned_values():
    profile = ROUNDING.model_copy(update={"modes": ("ROUND_HALF_UP", "ROUND_HALF_EVEN")})
    result = run((term(rounding=profile),))
    assert result.potential == Decimal("200") and result.trace["invariant"]
    assert len(result.trace["alternatives"]) == 2


@pytest.mark.parametrize(
    "profile",
    [
        ROUNDING.model_copy(update={"stage": "unknown"}),
        ROUNDING.model_copy(update={"alternatives_complete": False}),
    ],
)
def test_incomplete_rounding_bounds_block(profile):
    assert run((term(rounding=profile),)).reason == "ROUNDING_UNRESOLVED"


def test_one_cent_is_not_suppressed():
    result = run(
        (term(rate="10"),),
        bill(quantity="1", billed_rate="10.01", posted_amount="10.01", billed_gross="10.01"),
    )
    assert result.potential == Decimal("0.01")


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"quantity": None}, "QUANTITY_MISSING"),
        ({"currency": None}, "CURRENCY_MISMATCH"),
        ({"tax_basis": "unknown"}, "TAX_BASIS_UNRESOLVED"),
        ({"service_from": None}, "DATE_UNRESOLVED"),
        ({"date_conflict": True}, "DATE_UNRESOLVED"),
        ({"billed_discount": None}, "ACTUAL_BILLING_CONFLICT"),
        ({"credits": (credit("-10", None),)}, "CREDIT_ALLOCATION_UNRESOLVED"),
    ],
)
def test_conservative_gate_failures(changes, reason):
    result = run(billing=bill(**changes))
    assert result.reason == reason and result.potential is None


def test_known_missing_packet_blocks_without_assuming_uploaded_completeness():
    assert (
        run(governing=packet(known_missing=("incorporated schedule",))).reason
        == "PACKET_INCOMPLETE"
    )


def test_canonical_fingerprint_does_not_depend_on_dictionary_order():
    assert fingerprint({"a": None, "b": "0"}) == fingerprint({"b": "0", "a": None})
    assert fingerprint({"a": None}) != fingerprint({"a": "0"})


def test_unknown_end_date_and_party_meaning_do_not_become_defaults():
    assert run((term(open_ended=False),)).reason == "DATE_UNRESOLVED"
    assert run(billing=bill(supplier_party=None)).reason == "INPUT_CONFLICT"
    assert run((term(customer_party="different-buyer"),)).reason == "INPUT_CONFLICT"


def test_component_rounding_requires_and_reconciles_each_component():
    components = tuple(
        BaseComponent(
            key=k,
            contractual_gross="0.005",
            eligible=True,
            billed_gross="0.005",
            billed_discount="0",
            posted_amount="0.01",
        )
        for k in ("A", "B")
    )
    terms = (
        discount(
            "0",
            discount_base="sku_set",
            eligible_members=("A", "B"),
            rounding=ROUNDING.model_copy(update={"stage": "component"}),
        ),
    )
    billing = base_bill("0.01", "0.02", members=("A", "B"), base_components=components)
    result = run(terms, billing)
    assert result.expected == Decimal("0.02") and result.discrepancy == 0
    unknown = terms[0].model_copy(
        update={"rounding": ROUNDING.model_copy(update={"stage": "unknown"})}
    )
    assert run((unknown,), billing).reason == "ROUNDING_UNRESOLVED"


def test_large_finite_products_retain_source_precision_and_overflow_blocks():
    quantity = Decimal("1234567.890123")
    rate = Decimal("12345.678901")
    actual = (quantity * rate).quantize(Decimal("0.01"))
    result = run(
        (term(rate=rate),),
        bill(quantity=quantity, billed_rate=rate, billed_gross=None, posted_amount=actual),
    )
    assert result.expected == actual and Decimal(result.trace["expected_raw"]) == quantity * rate
    overflow = run(
        (term(rate="99999999999999"),),
        bill(
            quantity="99999999999999",
            billed_rate="1",
            billed_gross=None,
            posted_amount="99999999999999",
        ),
    )
    assert overflow.reason == "FINANCIAL_RANGE" and overflow.potential is None
