"""Pure, bounded Decimal calculation. No ORM, provider, HTTP, or legal inference."""

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal, Inexact, localcontext

from pydantic import TypeAdapter, ValidationError

from app.domain.money import Amount
from app.financial.schema import BillingScope, Packet, Term
from app.financial.values import MonetaryAmount, Percentage, Quantity, UnitPrice

COMPILER_VERSION = "reviewed-compiler/1"
RULE_VERSION = "core-bundle/1"
SNAPSHOT_VERSION = "financial-snapshot/1"
ARITHMETIC_PRECISION = 80
ZERO = Decimal("0")

MESSAGES = {
    "UNAPPROVED_FACT": "Review and approve the calculation inputs before assessment.",
    "PACKET_INCOMPLETE": "Review the missing or incomplete governing documents.",
    "PACKET_OUT_OF_SCOPE": "Approve packet coverage for this billing scope and period.",
    "AMBIGUOUS_MATCH": "Resolve the governing contract with source evidence.",
    "UNMATCHED": "Approve a source-supported contract association.",
    "CONFLICTING_IDENTIFIERS": "Resolve conflicting contract or purchase order identifiers.",
    "AMBIGUOUS_CONTRACT": "Resolve conflicting applicable terms with explicit precedence.",
    "UNSUPPORTED_RULE": "This pricing arrangement is outside the approved Phase 4 rules.",
    "DATE_UNRESOLVED": "Review the economic pricing date and its contractual basis.",
    "ALLOCATION_REQUIRED": "Approve quantity and billed amount for each price period.",
    "TERM_NOT_APPLICABLE": "Establish terms applicable to this economic date.",
    "RETROACTIVE_APPLICABILITY": "Approve the retroactive amendment's applicability.",
    "CURRENCY_MISMATCH": "Establish one identical, explicit currency for comparison.",
    "UNIT_MISMATCH": "Establish directly compatible contract and billed units.",
    "QUANTITY_MISSING": "Approve the billed quantity; it cannot be inferred from totals.",
    "FIXED_CYCLE_UNRESOLVED": "Approve the complete contractual billing cycle or event.",
    "DISCOUNT_BASE_UNRESOLVED": "Approve the complete eligible contractual discount base.",
    "TAX_BASIS_UNRESOLVED": "Establish comparable, explicitly separated pre-tax amounts.",
    "ACTUAL_BILLING_CONFLICT": "Reconcile billed prices, quantities, discounts and posted amounts.",
    "CREDIT_ALLOCATION_UNRESOLVED": "Resolve relevant credit allocation within this invoice.",
    "ROUNDING_UNRESOLVED": "Approve rounding precision and stage, or a complete invariant set.",
    "ROUNDING_MATERIAL": "Rounding alternatives change the result; review the applicable profile.",
    "FINANCIAL_RANGE": "The result exceeds supported financial precision or range.",
    "INPUT_CONFLICT": "Resolve the material input uncertainty before assessment.",
    "OVERLAPPING_SCOPE": "Resolve overlapping scope or credit allocations before assessment.",
    "STALE_INPUT": "Inputs changed. Reload approved revisions and evaluate again.",
}


def canonical(value: object) -> str:
    """Canonical JSON; schema payloads contain decimal strings, never binary floats."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def fingerprint(value: object) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


@dataclass(frozen=True)
class Result:
    outcome: str
    reason: str
    explanation: str
    currency: str | None = None
    expected: Decimal | None = None
    actual: Decimal | None = None
    discrepancy: Decimal | None = None
    potential: Decimal | None = None
    trace: dict | None = None


def blocked(reason: str, trace: dict | None = None) -> Result:
    return Result("NEEDS_REVIEW", reason, MESSAGES[reason], trace=trace)


def economic_interval(term: Term, bill: BillingScope):
    if bill.date_conflict or term.date_basis is None:
        return None
    if term.date_basis == "invoice":
        return (bill.invoice_date, None) if bill.invoice_date else None
    if term.date_basis == "event":
        return (bill.event_date, None) if bill.event_date else None
    if bill.service_from:
        return bill.service_from, bill.service_to
    if term.invoice_date_fallback and bill.invoice_date:
        return bill.invoice_date, None
    return None


def compile_terms(terms: tuple[Term, ...], bill: BillingScope, packet: Packet):
    """Select only explicit effective terms; keys are stable term identities."""
    if not packet.complete or packet.known_missing or packet.unresolved:
        return (), blocked("PACKET_INCOMPLETE")
    if (
        bill.scope not in packet.scopes
        or packet.effective_from is None
        or (packet.effective_to is None and not packet.open_ended)
    ):
        return (), blocked("PACKET_OUT_OF_SCOPE")
    if bill.unresolved:
        return (), blocked("INPUT_CONFLICT")
    scoped = [t for t in terms if t.scope == bill.scope]
    selected = []
    for term in scoped:
        interval = economic_interval(term, bill)
        if (
            interval is None
            or term.effective_from is None
            or (term.effective_to is None and not term.open_ended)
        ):
            return (), blocked("DATE_UNRESOLVED")
        start, end = interval
        if end is not None and end <= start:
            return (), blocked("DATE_UNRESOLVED")
        if start < packet.effective_from or (
            packet.effective_to
            and (start >= packet.effective_to or (end and end > packet.effective_to))
        ):
            return (), blocked("PACKET_OUT_OF_SCOPE")
        # Explicit interval crossing a change needs separately approved allocations.
        if end and (
            start < term.effective_from < end
            or (term.effective_to and start < term.effective_to < end)
        ):
            return (), blocked("ALLOCATION_REQUIRED")
        if start >= term.effective_from and (not term.effective_to or start < term.effective_to):
            selected.append(term)
    if not selected:
        return (), blocked("TERM_NOT_APPLICABLE")
    replaced = {key for t in selected for key in t.supersedes}
    # Cycles and self-supersession cannot establish a valid priority.
    if any(t.key in t.supersedes for t in selected) or all(t.key in replaced for t in selected):
        return (), blocked("AMBIGUOUS_CONTRACT")
    selected = [t for t in selected if t.key not in replaced]
    for term in selected:
        if term.unresolved:
            return (), blocked("AMBIGUOUS_CONTRACT")
        if term.retroactive and not term.retroactive_applicability_approved:
            return (), blocked("RETROACTIVE_APPLICABILITY")
        if term.family == "unsupported" or term.pricing_type not in {
            "fixed_unit",
            "fixed_cycle",
            "fixed_event",
            "unconditional_percentage",
        }:
            return (), blocked("UNSUPPORTED_RULE")
        if term.family == "percentage_discount" and term.unconditional is not True:
            return (), blocked("UNSUPPORTED_RULE")
    for term in selected:
        expected_types = {
            "unit_price": {"fixed_unit"},
            "fixed_fee": {"fixed_cycle", "fixed_event"},
            "percentage_discount": {"unconditional_percentage"},
        }
        if term.pricing_type not in expected_types.get(term.family, set()):
            return (), blocked("UNSUPPORTED_RULE")
    families = [t.family for t in selected]
    if len(families) != len(set(families)) or {"unit_price", "fixed_fee"} <= set(families):
        return (), blocked("AMBIGUOUS_CONTRACT")
    return tuple(sorted(selected, key=lambda t: t.key)), None


def evaluate(terms: tuple[Term, ...], bill: BillingScope, packet: Packet) -> Result:
    selected, error = compile_terms(terms, bill, packet)
    if error:
        return error
    if (
        not bill.supplier_party
        or not bill.customer_party
        or any(
            t.supplier_party != bill.supplier_party or t.customer_party != bill.customer_party
            for t in selected
        )
    ):
        return blocked("INPUT_CONFLICT")
    if not bill.currency or any(t.currency != bill.currency for t in selected):
        return blocked("CURRENCY_MISMATCH")
    if bill.tax_basis == "unknown" or any(t.tax_basis == "unknown" for t in selected):
        return blocked("TAX_BASIS_UNRESOLVED")
    if bill.posted_amount is None or bill.billed_discount is None:
        return blocked("ACTUAL_BILLING_CONFLICT")
    if bill.posted_amount < 0 or bill.billed_discount < 0:
        return blocked("ACTUAL_BILLING_CONFLICT")
    credits = bill.credits
    if len({c.key for c in credits}) != len(credits) or any(
        c.scope != bill.key or not c.within_invoice or c.amount >= 0 for c in credits
    ):
        return blocked("CREDIT_ALLOCATION_UNRESOLVED")
    profiles = [t.rounding for t in selected]
    if (
        any(p is None for p in profiles)
        or len({canonical(p.model_dump(mode="json")) for p in profiles if p}) != 1
    ):
        return blocked("ROUNDING_UNRESOLVED")
    profile = profiles[0]
    assert profile is not None
    if not profile.alternatives_complete or profile.stage == "unknown":
        return blocked("ROUNDING_UNRESOLVED")
    if bill.base_components and len({c.key for c in bill.base_components}) != len(
        bill.base_components
    ):
        return blocked("DISCOUNT_BASE_UNRESOLVED")
    try:
        with localcontext() as context:
            context.prec = ARITHMETIC_PRECISION
            context.traps[Inexact] = True
            base = None
            gross = bill.billed_gross
            discount = None
            formula = []
            for term in selected:
                if term.family == "unit_price":
                    if bill.quantity is None or bill.quantity <= 0:
                        return blocked("QUANTITY_MISSING")
                    if not term.unit or term.unit != bill.unit:
                        return blocked("UNIT_MISMATCH")
                    if term.rate is None or term.rate < 0 or bill.billed_rate is None:
                        return blocked("INPUT_CONFLICT")
                    if bill.billed_rate < 0:
                        return blocked("ACTUAL_BILLING_CONFLICT")
                    quantity = Quantity(bill.quantity, bill.unit)
                    base = (
                        UnitPrice(MonetaryAmount(term.rate, bill.currency), term.unit)
                        .extend(quantity)
                        .value
                    )
                    product = (
                        UnitPrice(MonetaryAmount(bill.billed_rate, bill.currency), bill.unit)
                        .extend(quantity)
                        .value
                    )
                    if gross is not None and gross != product:
                        return blocked("ACTUAL_BILLING_CONFLICT")
                    gross = product
                    formula.append("contracted unit price × billed quantity")
                elif term.family == "fixed_fee":
                    if term.rate is None or term.rate < 0:
                        return blocked("INPUT_CONFLICT")
                    if (
                        not term.full_cycle
                        or term.full_cycle != bill.cycle
                        or not bill.complete_cycle
                    ):
                        return blocked("FIXED_CYCLE_UNRESOLVED")
                    base = term.rate
                    formula.append("fixed fee for one approved complete cycle/event")
                else:
                    discount = term
            excluded = ZERO
            if discount:
                if (
                    discount.percentage is None
                    or not ZERO <= discount.percentage <= 100
                    or discount.discount_base is None
                ):
                    return blocked("DISCOUNT_BASE_UNRESOLVED")
                if discount.discount_base != "line" and (
                    bill.base_complete is not True
                    or not bill.base_components
                    or set(bill.members) != {c.key for c in bill.base_components}
                ):
                    return blocked("DISCOUNT_BASE_UNRESOLVED")
                if discount.discount_base == "sku_set" and set(discount.eligible_members) != {
                    c.key for c in bill.base_components if c.eligible
                }:
                    return blocked("DISCOUNT_BASE_UNRESOLVED")
                if base is None:
                    if not bill.base_components or bill.base_complete is not True:
                        return blocked("DISCOUNT_BASE_UNRESOLVED")
                    if any(c.contractual_gross < 0 for c in bill.base_components):
                        return blocked("DISCOUNT_BASE_UNRESOLVED")
                    base = sum(
                        (c.contractual_gross for c in bill.base_components if c.eligible), ZERO
                    )
                elif bill.base_components:
                    return blocked("DISCOUNT_BASE_UNRESOLVED")
                excluded = sum(
                    (c.contractual_gross for c in bill.base_components if not c.eligible), ZERO
                )
                expected_raw = (
                    Percentage(discount.percentage)
                    .reduce(MonetaryAmount(base, bill.currency))
                    .value
                    + excluded
                )
                formula.append(
                    "eligible contractual gross × (1 − unconditional percentage)"
                    " + explicitly excluded components"
                )
            elif base is not None:
                expected_raw = base
            else:
                return blocked("INPUT_CONFLICT")
            if gross is None or gross < 0:
                return blocked("ACTUAL_BILLING_CONFLICT")
            bridge = gross - bill.billed_discount
            actual = bill.posted_amount + sum((c.amount for c in credits), ZERO)
            if actual < 0:
                return blocked("CREDIT_ALLOCATION_UNRESOLVED")
            alternatives = []
            comparisons = set()
            for mode in profile.modes:
                # Rounding is deliberate only at this approved stage.
                with localcontext() as rounding_context:
                    rounding_context.traps[Inexact] = False
                    expected = expected_raw.quantize(profile.quantum, rounding=mode)
                    reconciled = bridge.quantize(profile.quantum, rounding=mode)
                    if profile.stage == "component" and bill.base_components:
                        if any(
                            c.billed_gross is None
                            or c.billed_discount is None
                            or c.posted_amount is None
                            for c in bill.base_components
                        ):
                            return blocked("ROUNDING_UNRESOLVED")
                        if (
                            sum((c.billed_gross for c in bill.base_components), ZERO) != gross
                            or sum((c.billed_discount for c in bill.base_components), ZERO)
                            != bill.billed_discount
                        ):
                            return blocked("ACTUAL_BILLING_CONFLICT")
                        expected_components = []
                        for component in bill.base_components:
                            component_expected = component.contractual_gross
                            if component.eligible and discount:
                                component_expected = (
                                    Percentage(discount.percentage)
                                    .reduce(MonetaryAmount(component_expected, bill.currency))
                                    .value
                                )
                            expected_components.append(
                                component_expected.quantize(profile.quantum, rounding=mode)
                            )
                            if (component.billed_gross - component.billed_discount).quantize(
                                profile.quantum, rounding=mode
                            ) != component.posted_amount:
                                return blocked("ACTUAL_BILLING_CONFLICT")
                        expected = sum(expected_components, ZERO)
                        reconciled = sum((c.posted_amount for c in bill.base_components), ZERO)
                if reconciled != bill.posted_amount:
                    return blocked("ACTUAL_BILLING_CONFLICT")
                delta = actual - expected
                for value in (expected, actual, delta):
                    TypeAdapter(Amount).validate_python(value)
                alternatives.append(
                    {
                        "mode": mode,
                        "expected": str(expected),
                        "actual": str(actual),
                        "discrepancy": str(delta),
                    }
                )
                comparisons.add(delta)
            if len(comparisons) != 1:
                return blocked("ROUNDING_MATERIAL", {"alternatives": alternatives})
            delta = next(iter(comparisons))
            outcome = (
                "POTENTIAL_LEAKAGE"
                if delta > 0
                else ("NO_OVERCHARGE" if delta == 0 else "UNDERCHARGE")
            )
            expected_values = {a["expected"] for a in alternatives}
            return Result(
                outcome,
                outcome,
                "Billed amount exceeds the applicable contracted amount."
                if delta > 0
                else (
                    "No overcharge in this assessed scope."
                    if delta == 0
                    else "Billed amount is below the contracted amount; no positive leakage."
                ),
                bill.currency,
                Decimal(next(iter(expected_values))) if len(expected_values) == 1 else None,
                actual,
                delta,
                delta if delta > 0 else None,
                {
                    "formula": " + ".join(formula),
                    "expected_raw": str(expected_raw),
                    "actual_bridge_raw": str(bridge),
                    "alternatives": alternatives,
                    "invariant": len(profile.modes) > 1,
                    "precision": ARITHMETIC_PRECISION,
                    "rules": [t.family for t in selected],
                    "economic_dates": {
                        t.key: [d.isoformat() if d else None for d in economic_interval(t, bill)]
                        for t in selected
                    },
                },
            )
    except (ValidationError, ArithmeticError):
        return blocked("FINANCIAL_RANGE")
