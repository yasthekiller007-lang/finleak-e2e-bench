"""Real PostgreSQL order tests: no shared-session simulation of financial races."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from decimal import Decimal as D
from threading import Event
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Organization, OrganizationMembership
from app.financial import service as financial
from app.financial.models import FinancialRevision
from app.financial.schema import FindingDecision, Review
from app.proof.budget import ProofError
from app.recovery import publication, service
from app.recovery.budget import Budget, admit
from app.recovery.models import RecoveryRecord
from app.recovery.schema import Approve, Lifecycle, Limits
from tests.financial_fixtures import term
from tests.recovery_fixtures import (
    db_session as db_session,
)
from tests.recovery_fixtures import (
    instrument,
    ok,
    post,
    prepare,
    ready,
    realization,
    report_body,
    setup,
)
from tests.recovery_fixtures import (
    recovery_engine as recovery_engine,
)
from tests.recovery_races import access_for
from tests.test_documents import api as api
from tests.test_financial_api import body
from tests.test_recovery_worked_examples import view

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    "change",
    [
        "membership",
        "finding",
        "fact",
        "packet",
        "association",
        "tax",
        "party",
        "pursuit",
        "closure",
    ],
)
@pytest.mark.parametrize("approval_first", [False, True])
def test_approval_serializes_every_calculation_and_recovery_authority(
    api, recovery_engine, change, approval_first
):
    f = setup(api)
    p, r = ready(api, f)
    i, v = instrument(api, f, "10000")
    q = prepare(api, f, realization(api, f, p, r, i, v, "10000"))
    access = access_for(api)
    engine = recovery_engine
    expected_head = UUID(q["authority"]["head"])
    changed = None
    if change in {"tax", "party", "pursuit"}:
        value = (
            v["value"]
            | {
                "previous_review_id": v["id"],
                "tax_basis": "UNKNOWN",
                "principal": None,
                "reconciliation": "UNRESOLVED",
            }
            if change == "tax"
            else {"kind": "party_revoked", "party_id": p["id"]}
            if change == "party"
            else r["value"] | {"pursuit": "5000"}
        )
        changed = prepare(api, f, value)
    revision = None
    data = None
    if change in {"fact", "packet", "association"}:
        kind = "term" if change == "fact" else change
        source = f["contract"] if kind in {"term", "packet"} else f["invoice"]
        revision = api["session"].scalar(
            select(FinancialRevision)
            .where(FinancialRevision.source_id == UUID(source), FinancialRevision.kind == kind)
            .order_by(FinancialRevision.number.desc())
        )
        payload = term(rate="60") if kind == "term" else dict(revision.payload["value"])
        if kind == "packet":
            payload["attestation"] = "Concurrently revised actual governing packet"
        data = Review.model_validate(
            body(
                kind,
                payload,
                f["cdoc"] if kind != "association" else f["idoc"],
                str(revision.id),
                "revoked" if kind == "association" else "approved",
            )
        )
    revision_source = revision.source_id if revision else None
    api["session"].commit()
    locked, attempting = Event(), Event()

    def transaction(approve):
        with Session(engine) as session:
            try:
                if approve == approval_first:
                    session.scalar(
                        select(Organization)
                        .where(Organization.id == access.organization_id)
                        .with_for_update()
                    )
                    locked.set()
                    assert attempting.wait(10)
                else:
                    assert locked.wait(10)
                    attempting.set()
                if approve:
                    result = service.execute(
                        session,
                        access,
                        "approve",
                        UUID(q["id"]),
                        Approve(
                            expected_head=expected_head,
                            reason="Pinned independent concurrent approval",
                        ),
                        uuid4(),
                        api["app"].state.storage,
                        api["app"].state.settings.recovery_limits,
                    )
                elif change == "membership":
                    session.scalar(
                        select(Organization)
                        .where(Organization.id == access.organization_id)
                        .with_for_update()
                    )
                    membership = session.scalar(
                        select(OrganizationMembership).where(
                            OrganizationMembership.organization_id == access.organization_id,
                            OrganizationMembership.user_id == access.user_id,
                        )
                    )
                    membership.role = "viewer"
                    session.flush()
                    result = {"changed": True}
                elif change == "finding":
                    financial.decide(
                        session,
                        access,
                        UUID(f["evaluation"]["id"]),
                        FindingDecision(
                            status="needs_review",
                            reason="Concurrent independent financial review",
                            expected_decision=f["decision"]["id"],
                        ),
                    )
                    result = {"changed": True}
                elif change in {"fact", "packet", "association"}:
                    financial.review(session, access, revision_source, data, uuid4())
                    result = {"changed": True}
                elif changed:
                    result = service.execute(
                        session,
                        access,
                        "approve",
                        UUID(changed["id"]),
                        Approve(
                            expected_head=expected_head,
                            reason="Concurrent approved authority revision",
                        ),
                        uuid4(),
                        api["app"].state.storage,
                        api["app"].state.settings.recovery_limits,
                    )
                else:
                    result = service.execute(
                        session,
                        access,
                        "lifecycle",
                        UUID(f["case"]["id"]),
                        Lifecycle(
                            state="CLOSED",
                            closure_reason="MANAGEMENT",
                            expected_head=expected_head,
                            reason="Concurrent explicit closure",
                        ),
                        uuid4(),
                        api["app"].state.storage,
                        api["app"].state.settings.recovery_limits,
                    )
                session.commit()
                return result
            except (HTTPException, ProofError) as exc:
                session.rollback()
                return {"error": getattr(exc, "code", "FORBIDDEN")}

    with ThreadPoolExecutor(max_workers=2) as pool:
        approval = pool.submit(transaction, True)
        mutation = pool.submit(transaction, False)
        approved_result, changed_result = approval.result(timeout=20), mutation.result(timeout=20)
    with Session(engine) as session:
        realized = session.scalar(
            select(func.coalesce(func.sum(RecoveryRecord.amount), 0)).where(
                RecoveryRecord.kind == "realization"
            )
        )
        assert realized == (D("10000") if approval_first else D("0"))
        if approval_first:
            row = session.scalar(select(RecoveryRecord).where(RecoveryRecord.kind == "realization"))
            assert (
                row.pins["decision_id"] == f["decision"]["id"] and row.pins["party_id"] == p["id"]
            )
    assert ("error" not in approved_result) == approval_first
    if not approval_first:
        assert "error" not in changed_result


def test_as_known_excludes_transaction_that_committed_after_cutoff(api, recovery_engine):
    f = setup(api)
    p, r = ready(api, f)
    i, v = instrument(api, f, "10000")
    q = prepare(api, f, realization(api, f, p, r, i, v, "10000"))
    access = access_for(api)
    api["session"].commit()
    with Session(recovery_engine) as session:
        result = service.execute(
            session,
            access,
            "approve",
            UUID(q["id"]),
            Approve(expected_head=q["authority"]["head"], reason="Actual commit boundary test"),
            uuid4(),
            api["app"].state.storage,
            api["app"].state.settings.recovery_limits,
        )
        cutoff = datetime.now(UTC).isoformat()
        assert result["known_at"] is None
        session.commit()
        budget = Budget(Limits())
        publication.capture(session, access, budget)
        session.commit()
    old = ok(post(api, "/report", report_body(known_at=cutoff)))
    now = ok(post(api, "/report", report_body()))
    assert D(old["realized_flow"]) == 0 and D(now["realized_flow"]) == 10000


def test_two_tenant_slots_are_shared_by_independent_workers(api, recovery_engine):
    f = setup(api)
    access = access_for(api)
    api["session"].commit()
    with (
        Session(recovery_engine) as one,
        Session(recovery_engine) as two,
        Session(recovery_engine) as third,
    ):
        admit(one, access, Budget(Limits()))
        admit(two, access, Budget(Limits()))
        with pytest.raises(ProofError, match="recovery_busy"):
            admit(third, access, Budget(Limits()))
        third.rollback()
        one.rollback()
        admit(third, access, Budget(Limits()))
        third.rollback()
        two.rollback()
    assert D(view(api, f)["realized"]) == 0


def test_actor_quota_is_shared_across_tenants_and_retry_does_not_consume(api):
    from app.recovery.budget import quota
    from app.recovery.models import RecoveryRequest

    f = setup(api)
    access = access_for(api)
    api["session"].commit()
    session = api["session"]
    session.add(
        OrganizationMembership(
            organization_id=api["orgs"]["b"], user_id=access.user_id, role="owner"
        )
    )
    session.commit()
    other = type(access)(api["orgs"]["b"], access.user_id, access.role)
    for n in range(10):
        session.add(
            RecoveryRequest(
                organization_id=access.organization_id if n % 2 else other.organization_id,
                actor_id=access.user_id,
                audit_id=uuid4(),
                request_key=uuid4(),
                request_hash="f" * 64,
                command="approve",
                counted=True,
                result={"synthetic_authority_attempt": True},
            )
        )
        session.commit()
    for actor_access in (access, other):
        with pytest.raises(ProofError, match="recovery_rate_limit"):
            quota(session, actor_access, Budget(Limits()))
        session.rollback()
    assert D(view(api, f)["realized"]) == 0


def test_cumulative_sql_work_budget_includes_flush_and_lock_queries(api, monkeypatch):
    import time

    from app.proof.budget import ProofError
    from app.recovery.budget import Budget

    f = setup(api)
    access = access_for(api)
    budget = Budget(Limits())
    admit(api["session"], access, budget)
    budget.started = time.monotonic() - 26
    with pytest.raises(ProofError, match="recovery_work_budget"):
        api["session"].scalar(select(func.count()).select_from(RecoveryRecord))
    api["session"].info.pop("recovery_budget", None)
    api["session"].connection().info.pop("recovery_budget", None)
    api["session"].rollback()
    assert D(view(api, f)["realized"]) == 0
