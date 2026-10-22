"""Bounded, reproducible projections. No aggregate authority or export artifact."""

from datetime import UTC, datetime
from uuid import UUID

from app.proof.budget import ProofError
from app.recovery import publication, service
from app.recovery.models import RecoveryCase, RecoveryPublication, RecoveryRecord
from app.recovery.schema import Moment
from app.recovery.values import ZERO, fail, in_period, instant, percentage, subtract, total


def last(rows, kind):
    return next((r for r in reversed(rows) if r.kind == kind), None)


def projection(case, evaluation, rows, observation):
    ready = last(rows, "readiness")
    lifecycle = last(rows, "lifecycle")
    claim = last(rows, "claim")
    vendor = last(rows, "vendor")
    compatible_vendor = (
        vendor
        and vendor.value["tax_basis"] == "EXCLUSIVE"
        and vendor.value["currency"] == evaluation.currency
    )
    approved = [r for r in rows if r.kind in {"realization", "reversal"}]
    realized = total([r.amount for r in approved])
    methods = {}
    for row in approved:
        method = row.value.get("method")
        if row.kind == "reversal":
            original = next(r for r in rows if r.id == row.original_id)
            method = original.value["method"]
        methods[method] = total([methods.get(method, ZERO), row.amount])
    party = last(rows, "party")
    reviewed = {r.instrument_id: r for r in rows if r.kind == "instrument"}
    unresolved = any(
        r.value.get("reconciliation") == "UNRESOLVED"
        or (
            r.kind == "instrument"
            and (
                r.principal is None
                or r.currency != evaluation.currency
                or len(r.value["related_cases"]) > 1
                or r.value["status"] == "UNRESOLVED"
                or (
                    party is not None
                    and any(r.value[k] != party.value[k] for k in ("payer", "payee", "beneficiary"))
                )
            )
        )
        for r in rows
        if (r.kind == "instrument" and reviewed[r.instrument_id].id == r.id)
        or (
            r.kind == "realization"
            and r.value.get("reconciliation") == "UNRESOLVED"
            and reviewed.get(r.instrument_id)
            and reviewed[r.instrument_id].value["reconciliation"] == "UNRESOLVED"
        )
    )
    known = observation or {
        "currentness": "UNKNOWN",
        "finding_decision": "UNKNOWN",
        "integrity": "UNCHECKED",
        "authority": "UNKNOWN",
    }
    current = known["currentness"] == "CURRENT" and known["finding_decision"] == "confirmed"
    evidence_ok = known["integrity"] == "VERIFIED"
    v = evaluation.potential if current else None
    pursuit = ready.principal if ready else None
    balance_known = pursuit is not None and not unresolved
    eligible = (
        current
        and evidence_ok
        and known.get("authority") == "VALID"
        and ready is not None
        and not unresolved
        and last(rows, "retire") is None
    )
    blocked_lifecycle = lifecycle and (
        lifecycle.value["state"] != "OPEN" or lifecycle.number > (ready.number if ready else 0)
    )
    readiness = (
        "READY" if eligible and not blocked_lifecycle else "BLOCKED" if ready else "INVESTIGATION"
    )
    category = (
        "ACTIVE_ELIGIBLE"
        if eligible
        else "INVALIDATED_BASIS"
        if known["finding_decision"] == "false_positive"
        else "STALE_BASIS"
        if known["currentness"] == "STALE"
        else "EVIDENCE_EXCEPTION"
        if not evidence_ok
        else "INCOMPLETE_AUTHORITY"
    )
    costs = {}
    for row in rows:
        if row.kind != "cost":
            continue
        group = costs.setdefault(row.currency, {"incurred": ZERO, "paid": ZERO})
        if row.value["state"] == "REVERSED":
            original = next(r for r in rows if r.id == row.original_id)
            field = original.value["state"].lower()
            group[field] = subtract(group[field], row.principal)
        else:
            field = row.value["state"].lower()
            group[field] = total([group[field], row.principal])
    cash_blocker = None
    try:
        cash_entries = net_cash_entries(rows)
    except ProofError as exc:
        if exc.code != "recovery_economic_date_unresolved":
            raise
        cash_entries, cash_blocker, unresolved, eligible = [], exc.code, True, False
        balance_known = False
        readiness, category = "BLOCKED", "INCOMPLETE_AUTHORITY"
    n = total([amount for amount, _ in cash_entries]) if cash_entries else None
    state = (
        "UNKNOWN"
        if unresolved
        else "NO_APPROVED"
        if realized == ZERO
        else "AT_PURSUIT_CEILING"
        if pursuit == realized
        else "PARTIAL"
    )
    return {
        "id": str(case.id),
        "evaluation_id": str(evaluation.id),
        "head_id": str(rows[-1].id) if rows else None,
        "currency": evaluation.currency,
        "supplier": evaluation.snapshot["billing_scope"]["supplier_party"],
        "customer": evaluation.snapshot["billing_scope"]["customer_party"],
        "tax_basis": "EXCLUSIVE",
        "lifecycle": lifecycle.value["state"] if lifecycle else "OPEN",
        "readiness": readiness,
        "finding_decision": known["finding_decision"],
        "currentness": known["currentness"],
        "evidence": known["integrity"],
        "authority": known.get("authority", "UNKNOWN"),
        "authority_blocker": known.get("authority_blocker"),
        "realization_state": state,
        "category": category,
        "coverage": "UNRESOLVED" if unresolved else "COMPLETE_RECORDED_LEDGER",
        "potential": str(evaluation.potential),
        "validated": str(v) if v is not None else None,
        "pursuit": str(pursuit) if pursuit is not None else None,
        "claimed": str(claim.principal)
        if claim and claim.value["state"] == "RECORDED_ACTION" and claim.principal is not None
        else None,
        "claim_state": claim.value["state"] if claim else "NONE",
        "acknowledged": vendor.value.get("acknowledged") if compatible_vendor else None,
        "disputed": vendor.value.get("disputed") if compatible_vendor else None,
        "vendor_position": service.serialize(vendor) if vendor else None,
        "vendor_state": vendor.value["state"] if vendor else "NO_RESPONSE",
        "realized": str(realized),
        "realized_label": "Gross verified realized recovery — before separately evidenced costs",
        "methods": {k: str(v) for k, v in methods.items()},
        "net_cash": str(n) if n is not None else None,
        "net_cash_blocker": cash_blocker,
        "pending_credit": pending_credit(rows, evaluation.currency),
        "unrealized": str(subtract(pursuit, realized)) if balance_known else None,
        "ratio": percentage(realized, v) if eligible else None,
        "ratio_inputs": {"numerator": str(realized), "denominator": str(v)} if eligible else None,
        "costs": {c: {k: str(v) for k, v in data.items()} for c, data in costs.items()},
        "workflow": last(rows, "workflow").value if last(rows, "workflow") else None,
        "readiness_record": service.serialize(ready) if ready else None,
        "limitations": (
            "Manual reviewed evidence; no accounting posting, tax recoverability, "
            "forecast, gain-share or external delivery."
        ),
    }


def current_observation(session, access, case, rows, storage, budget):
    evaluation, decision, stale = service.finding_state(session, access, case)
    value = {
        "currentness": "STALE" if stale else "CURRENT",
        "finding_decision": decision.status if decision else "detected",
        "decision_id": str(decision.id) if decision else None,
        "integrity": "UNCHECKED",
        "authority": "UNKNOWN",
    }
    ready = last(rows, "readiness")
    if ready:
        try:
            package = service.get(
                session, access, service.ProofPackage, UUID(ready.value["proof_id"])
            )
            service.proof.assert_package(session, access, package)
            proposal_ids = [
                r.proposal_id
                for r in rows
                if r.proposal_id and r.kind not in {"rejected", "withdrawn"}
            ]
            service.verified_sources(session, access, proposal_ids, package, storage, budget)
            value["integrity"] = "VERIFIED"
            try:
                service.authority(session, access, case, ready.value, storage, budget, proposal_ids)
                value["authority"] = "VALID"
            except ProofError as exc:
                if exc.code in {"recovery_resource_limit", "recovery_work_budget"}:
                    raise
                value["authority"] = "BLOCKED"
                value["authority_blocker"] = exc.code
        except ProofError as exc:
            if exc.code in {"recovery_resource_limit", "recovery_work_budget"}:
                raise
            value["integrity"] = "UNAVAILABLE_OR_MISMATCH"
    return evaluation, value


def detail(session, access, case, storage, budget):
    rows = service.records(session, access, case.id, budget)
    evaluation, value = current_observation(session, access, case, rows, storage, budget)
    return projection(case, evaluation, rows, value)


def before_end(moment, end, timezone):
    end = Moment.model_validate(end)
    if end.precision == "LOCAL":
        end = Moment(precision="INSTANT", timestamp=instant(end))
    beginning = (
        Moment(precision="DATE", day="0001-01-01")
        if end.precision == "DATE"
        else Moment(precision="INSTANT", timestamp=datetime(1, 1, 1, tzinfo=UTC))
    )
    return in_period(moment, beginning, end, timezone)


def pending_credit(rows, currency, before=None):
    """Physical credit stock, with dated corrections and no partial unknown total.

    De-recognition releases finding attribution, not AP availability. A supported
    replacement moves only its corrected portion's economic consumption date.
    The original as-known history remains unchanged.
    """

    def included(row):
        return before is None or row.economic is None or before(row.economic)

    reviews = {
        r.instrument_id: r
        for r in rows
        if r.kind == "instrument" and r.pins.get("instrument_kind") == "CREDIT" and included(r)
    }
    pending = {}
    for identity, review in reviews.items():
        if review.currency != currency:
            continue
        if (
            review.principal is None
            or review.value["reconciliation"] != "COMPLETE"
            or review.value["status"] == "UNRESOLVED"
        ):
            return None
        if review.value["status"] == "ISSUED":
            pending[identity] = review.principal
    allocations = {r.id: r for r in rows if r.kind == "realization"}
    children = {}
    for row in allocations.values():
        if row.value.get("replaces_id"):
            children.setdefault(UUID(row.value["replaces_id"]), []).append(row)
    for row in rows:
        if row.instrument_id not in pending:
            continue
        if row.kind == "realization":
            # Each correction replaces part of its parent's consumption date.
            unchanged = subtract(row.amount, total([r.amount for r in children.get(row.id, [])]))
            if unchanged < ZERO:
                fail("recovery_integrity_conflict")
            if included(row):
                pending[row.instrument_id] = subtract(pending[row.instrument_id], unchanged)
        elif row.kind == "credit_state" and included(row):
            if row.value["state"] in {"CANCELLED", "EXPIRED"}:
                pending[row.instrument_id] = subtract(pending[row.instrument_id], row.principal)
            elif row.value["state"] == "RESTORED":
                pending[row.instrument_id] = total([pending[row.instrument_id], row.principal])
    return str(total(pending.values())) if pending else None


def net_cash_entries(rows):
    # Attribution corrections never fabricate bank outflows or a second receipt.
    # An explicit successor correction may repair the evidenced economic date of
    # the same physical receipt. Its original net cash remains unchanged.
    original = {r.id: r for r in rows if r.kind == "realization" and not r.value.get("replaces_id")}
    dates = {identity: row.economic for identity, row in original.items()}
    roots = {identity: identity for identity in original}
    for row in rows:
        if row.kind == "realization" and row.value.get("replaces_id"):
            ancestor = roots.get(UUID(row.value["replaces_id"]))
            if ancestor:
                roots[row.id] = ancestor
                dates[ancestor] = row.economic
    result, cash_roots = [], {}
    for identity, row in original.items():
        if row.net_cash is None:
            continue
        if row.pins.get("instrument_kind") == "CASH":
            if row.instrument_id in cash_roots:
                if cash_roots[row.instrument_id] != dates[identity]:
                    fail("recovery_economic_date_unresolved", "Receipt date corrections disagree")
                continue
            cash_roots[row.instrument_id] = dates[identity]
        result.append((row.net_cash, dates[identity]))
    result += [
        (r.net_cash, r.economic) for r in rows if r.kind == "reversal" and r.net_cash is not None
    ]
    return result


def report(session, access, body, budget):
    # One bounded complete population, never a page-derived authoritative total.
    if body.known_at > session.scalar(service.select(service.func.clock_timestamp())):
        fail("recovery_known_at_future", "Knowledge cutoff must not be in the future", 422)
    cases = session.scalars(
        service.query(RecoveryCase, access)
        .join(
            RecoveryPublication,
            (RecoveryPublication.case_id == RecoveryCase.id)
            & (RecoveryPublication.organization_id == RecoveryCase.organization_id),
        )
        .where(RecoveryPublication.committed_at <= body.known_at)
        .order_by(RecoveryCase.id)
        .limit(budget.limits.projection_records + 1)
    ).all()
    budget.bound(len(cases), "projection_records")
    rows = session.scalars(
        service.query(RecoveryRecord, access)
        .join(
            RecoveryPublication,
            (RecoveryPublication.record_id == RecoveryRecord.id)
            & (RecoveryPublication.organization_id == RecoveryRecord.organization_id),
        )
        .where(RecoveryPublication.committed_at <= body.known_at)
        .order_by(RecoveryPublication.committed_at, RecoveryRecord.id)
        .limit(budget.limits.projection_records + 1)
    ).all()
    budget.bound(len(rows) + len(cases), "projection_records")
    items, selected, occupied = [], [], set()
    flow, active_r, active_v, exception_r, cash_flow = ZERO, ZERO, ZERO, ZERO, ZERO
    complete = True
    for row in [*cases, *rows]:
        service.assert_origin(session, access, row)
    for case in cases:
        evaluation = service.financial.get_evaluation(session, access, case.evaluation_id)
        if (
            evaluation.currency != body.currency
            or evaluation.snapshot["billing_scope"]["customer_party"] != body.customer
        ):
            continue
        history = sorted([r for r in rows if r.case_id == case.id], key=lambda r: r.number)
        observation = last(history, "observation")
        stock_history = [
            r
            for r in history
            if r.economic is None or before_end(r.economic, body.end, body.timezone)
        ]
        item = projection(
            case, evaluation, stock_history, observation.value if observation else None
        )
        item["pending_credit"] = pending_credit(
            history, evaluation.currency, lambda when: before_end(when, body.end, body.timezone)
        )
        cash_entries = net_cash_entries(history)
        cash_stock = [
            amount for amount, when in cash_entries if before_end(when, body.end, body.timezone)
        ]
        item["net_cash"] = str(total(cash_stock)) if cash_stock else None
        cash_flow = total(
            [
                cash_flow,
                *[
                    amount
                    for amount, when in cash_entries
                    if in_period(when, body.start, body.end, body.timezone)
                ],
            ]
        )
        members = {
            (str(evaluation.invoice_source_id), member)
            for member in evaluation.snapshot["billing_scope"]["members"]
        }
        if item["category"] == "ACTIVE_ELIGIBLE" and occupied & members:
            item["category"] = "OVERLAPPING_AUTHORITY"
            item["ratio"] = None
        if item["category"] == "ACTIVE_ELIGIBLE":
            occupied.update(members)
            active_r = total([active_r, service.exact(item["realized"])])
            active_v = total([active_v, service.exact(item["validated"])])
        else:
            exception_r = total([exception_r, service.exact(item["realized"])])
            if item["currentness"] == "UNKNOWN" or item["coverage"] == "UNRESOLVED":
                complete = False
        for row in history:
            selected.append(str(row.id))
            if row.kind in {"realization", "reversal"} and in_period(
                row.economic, body.start, body.end, body.timezone
            ):
                flow = total([flow, row.amount])
        items.append(item)
    context = {
        "tenant": str(access.organization_id),
        "profile": budget.limits.profile,
        "known_at": body.known_at.isoformat(),
        "period": {
            "start": body.start.model_dump(mode="json"),
            "end": body.end.model_dump(mode="json"),
            "timezone": body.timezone,
            "boundary": "[start,end)",
        },
        "currency": body.currency,
        "customer": body.customer,
        "tax_basis": body.tax_basis,
        "record_ids": sorted(selected),
        "high_watermark": publication.committed(session, access, rows[-1].id).isoformat()
        if rows
        else None,
        "coverage": "COMPLETE" if complete else "UNKNOWN_OR_UNRESOLVED",
    }
    result = {
        "context": context,
        "items": items,
        "realized_flow": str(flow),
        "net_cash_flow": str(cash_flow),
        "active_eligible_realized": str(active_r),
        "matching_validated": str(active_v),
        "historical_exception_realized": str(exception_r),
        "ratio": percentage(active_r, active_v) if complete else None,
        "ratio_inputs": {"numerator": str(active_r), "denominator": str(active_v)}
        if complete
        else None,
    }
    result["digest"] = service.digest(result)
    budget.bound(len(service.canonical(result)), "response_bytes")
    return result
