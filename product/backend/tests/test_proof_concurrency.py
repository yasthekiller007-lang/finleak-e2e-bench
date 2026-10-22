from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.financial import service as financial
from app.financial.models import FinancialAudit
from app.financial.schema import Evaluate, Review
from app.modules.storage import LocalObjectStorage
from app.proof import service
from app.proof.budget import Budget, ProofError
from app.proof.models import ProofPackage
from app.proof.schema import Event as ProofCommand
from app.proof.schema import Generate, OperationalLimits
from tests.test_financial_api import body
from tests.test_financial_concurrency import financial_database as financial_database

pytestmark = pytest.mark.integration


@pytest.fixture
def proof_database(financial_database, tmp_path):
    engine, access, cid, iid, cdoc, idoc, approvals, pinned = financial_database
    # The shared concurrency fixture now migrates the full current runtime chain.
    with Session(engine) as session:
        evaluation = financial.evaluate_scope(
            session, access, iid, Evaluate(scope_key="line-1", expected_revisions=tuple(pinned))
        )
        evaluation_id, fp = evaluation.id, evaluation.fingerprint
        session.commit()
    # This historical fixture has intentionally unavailable originals. It must yield an
    # INCOMPLETE package, not fabricated verified bytes; API tests exercise actual originals.
    return (
        engine,
        access,
        evaluation_id,
        Generate(expected_fingerprint=fp),
        LocalObjectStorage(tmp_path),
        cid,
        iid,
        cdoc,
        idoc,
        approvals,
    )


def execute(data, *, key=None, body_override=None):
    engine, access, evaluation_id, request, storage, *_ = data
    with Session(engine) as session:
        result = service.execute(
            session,
            access,
            "generate",
            evaluation_id,
            body_override or request,
            key or uuid4(),
            storage,
            OperationalLimits(),
        )
        session.commit()
        return result


@pytest.mark.parametrize("same_key", [True, False])
def test_simultaneous_generation_semantic_identity_and_single_audit(proof_database, same_key):
    barrier = Barrier(2)
    key = uuid4()

    def start():
        barrier.wait(timeout=5)
        return execute(proof_database, key=key if same_key else uuid4())

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(start) for _ in range(2)]
        results = [future.result(timeout=10) for future in futures]
    assert results[0]["package_id"] == results[1]["package_id"]
    if same_key:
        assert results[0] == results[1]
        assert execute(proof_database, key=key) == results[0]
    with Session(proof_database[0]) as session:
        assert session.scalar(select(func.count()).select_from(ProofPackage)) == 1
        assert (
            session.scalar(
                select(func.count())
                .select_from(FinancialAudit)
                .where(FinancialAudit.action == "proof.issued")
            )
            == 1
        )


@pytest.mark.parametrize(
    "kind,state",
    [(kind, "revoked") for kind in ("term", "packet", "association")]
    + [("term", "approved"), ("packet", "approved")],
)
def test_committed_approval_packet_or_association_revocation_blocks_current_generation(
    proof_database, kind, state
):
    engine, access, _, request, _, cid, iid, cdoc, idoc, approvals = proof_database
    locked = Event()
    release = Event()

    def change():
        with Session(engine) as session:
            previous = session.get(
                __import__(
                    "app.financial.models", fromlist=["FinancialRevision"]
                ).FinancialRevision,
                approvals[{"term": 0, "packet": 1, "association": 3}[kind]],
            )
            value = previous.payload["value"].copy()
            if state == "approved":
                value.update(
                    {"rate": "11"}
                    if kind == "term"
                    else {"known_missing": ["New governing schedule"]}
                )
            data = body(
                kind,
                value,
                cdoc if kind != "association" else idoc,
                previous=str(previous.id),
                state=state,
            )
            financial.review(
                session,
                access,
                cid if kind != "association" else iid,
                Review.model_validate(data),
                uuid4(),
            )
            locked.set()
            assert release.wait(timeout=5)
            session.commit()

    with ThreadPoolExecutor(max_workers=2) as pool:
        revision = pool.submit(change)
        assert locked.wait(timeout=5)
        generation = pool.submit(execute, proof_database)
        assert not generation.done()
        release.set()
        revision.result(timeout=10)
        result = generation.result(timeout=10)
    assert result["error"]["code"] == "proof_historical_required"
    historical = request.model_copy(update={"mode": "HISTORICAL"})
    assert "package_id" in execute(proof_database, body_override=historical)
    with Session(engine) as session:
        package = session.scalar(select(ProofPackage))
        assert package.core["identity"]["evaluation_fingerprint"] == request.expected_fingerprint


def test_membership_revocation_committed_before_generation_is_rechecked(proof_database):
    engine, access, *_ = proof_database
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE organization_memberships SET role='viewer' "
                "WHERE organization_id=:org AND user_id=:actor"
            ),
            {"org": access.organization_id, "actor": access.user_id},
        )
    with pytest.raises(HTTPException) as exc:
        execute(proof_database)
    assert exc.value.status_code == 403
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(ProofPackage)) == 0


def test_active_generation_holds_membership_authority_until_commit(proof_database, monkeypatch):
    engine, access, *_ = proof_database
    captured, release, revocation_started = Event(), Event(), Event()
    original = service.verify_source

    def wait(*args, **kwargs):
        captured.set()
        assert release.wait(timeout=5)
        return original(*args, **kwargs)

    monkeypatch.setattr(service, "verify_source", wait)

    def revoke():
        with engine.begin() as connection:
            revocation_started.set()
            connection.execute(
                text(
                    "UPDATE organization_memberships SET role='viewer' "
                    "WHERE organization_id=:org AND user_id=:actor"
                ),
                {"org": access.organization_id, "actor": access.user_id},
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        generation = pool.submit(execute, proof_database)
        assert captured.wait(timeout=5)
        revoked = pool.submit(revoke)
        assert revocation_started.wait(timeout=5)
        assert not revoked.done()
        release.set()
        assert "package_id" in generation.result(timeout=10)
        revoked.result(timeout=10)


def test_two_postgres_slots_are_shared_across_connections_and_release_on_rollback(proof_database):
    engine, access, *_ = proof_database
    with Session(engine) as first, Session(engine) as second, Session(engine) as third:
        service.admit(first, access, Budget(OperationalLimits()))
        service.admit(second, access, Budget(OperationalLimits()))
        with pytest.raises(ProofError, match="proof_busy"):
            service.admit(third, access, Budget(OperationalLimits()))
        first.rollback()
        service.admit(third, access, Budget(OperationalLimits()))


@pytest.mark.parametrize("kind", ["review.finalized", "disclosure.approved"])
def test_simultaneous_final_review_and_disclosure_approval_have_one_authoritative_head(
    proof_database, kind
):
    engine, access, *_ = proof_database
    package_id = execute(proof_database)["package_id"]
    from uuid import UUID

    package_id = UUID(package_id)
    previous = None
    if kind == "disclosure.approved":
        with Session(engine) as session:
            proposal = service.execute(
                session,
                access,
                "disclosure.proposed",
                package_id,
                ProofCommand(
                    kind="disclosure.proposed",
                    text="Hide source identity",
                    paths=["/identity/invoice_source_id"],
                ),
                uuid4(),
                proof_database[4],
                OperationalLimits(),
            )
            previous = proposal["event_id"]
            session.commit()
    barrier = Barrier(2)

    def approve():
        with Session(engine) as session:
            barrier.wait(timeout=5)
            result = service.execute(
                session,
                access,
                kind,
                package_id,
                ProofCommand(
                    kind=kind,
                    text="Attributed review",
                    previous_id=previous,
                    status="REVIEWED" if kind == "review.finalized" else None,
                ),
                uuid4(),
                proof_database[4],
                OperationalLimits(),
            )
            session.commit()
            return result

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(approve) for _ in range(2)]
        results = [future.result(timeout=10) for future in futures]
    assert sum("event_id" in result for result in results) == 1
    assert next(result["error"]["code"] for result in results if "error" in result) == (
        "proof_stale_revision"
    )
