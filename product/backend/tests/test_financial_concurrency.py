import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from uuid import UUID, uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import HTTPException
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session

from app.auth.dependencies import OrganizationAccess
from app.db.base import Base
from app.db.models import Document, Organization, OrganizationMembership, User
from app.domain.types import DocumentType, MembershipRole, ProcessingStatus
from app.financial import service
from app.financial.models import FinancialAudit, FinancialEvaluation
from app.financial.schema import CreateSource, Evaluate, Review
from tests.financial_fixtures import bill, packet, term
from tests.test_financial_api import body
from tests.test_phase2_migration import migration

pytestmark = pytest.mark.integration


@pytest.fixture
def financial_database():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set isolated TEST_DATABASE_URL")
    admin = create_engine(url)
    schema = "financial_concurrency_" + uuid4().hex
    with admin.begin() as connection:
        connection.execute(text(f"CREATE SCHEMA {schema}"))
        connection.execute(text(f"SET LOCAL search_path TO {schema}"))
        with Operations.context(
            MigrationContext.configure(connection, opts={"target_metadata": Base.metadata})
        ):
            for name in [
                "0001_initial_tenant_scoped_financial_schema.py",
                "0002_identity_membership_uploads.py",
                "0003_document_intelligence.py",
                "0004_reviewed_financial_engine.py",
                "0005_leakage_proof_engine.py",
                "0006_recovery_ledger.py",
                "0007_pilot_access.py",
                "0008_pilot_intake.py",
                "0009_source_quarantine.py",
            ]:
                migration(name).upgrade()
    engine = create_engine(
        url, connect_args={"options": f"-c search_path={schema} -c statement_timeout=10000"}
    )
    org, actor, cdoc, idoc = uuid4(), uuid4(), uuid4(), uuid4()
    access = OrganizationAccess(org, actor, MembershipRole.OWNER)
    try:
        with Session(engine) as session:
            session.add_all(
                [
                    Organization(id=org, name="Synthetic concurrency tenant"),
                    User(id=actor, display_name="Synthetic approver"),
                ]
            )
            session.flush()
            session.add(OrganizationMembership(organization_id=org, user_id=actor, role="owner"))
            for doc, kind, sha in [
                (cdoc, DocumentType.CONTRACT, "a"),
                (idoc, DocumentType.INVOICE, "b"),
            ]:
                session.add(
                    Document(
                        id=doc,
                        organization_id=org,
                        original_filename="synthetic.csv",
                        mime_type="text/csv",
                        file_size=1,
                        storage_key=str(doc),
                        sha256=sha * 64,
                        document_type=kind,
                        processing_status=ProcessingStatus.PROCESSED,
                    )
                )
            session.flush()
            contract = service.create_source(
                session, access, CreateSource(document_id=cdoc, kind="contract")
            )
            invoice = service.create_source(
                session, access, CreateSource(document_id=idoc, kind="invoice")
            )
            cid, iid = contract.id, invoice.id
            approvals = []
            for sid, data in [
                (cid, body("term", term(), cdoc)),
                (
                    cid,
                    body(
                        "packet", packet(documents=({"document_id": cdoc, "role": "master"},)), cdoc
                    ),
                ),
                (iid, body("billing_scope", bill(), idoc)),
                (
                    iid,
                    body(
                        "association",
                        {
                            "contract_source_id": str(cid),
                            "method": "manual",
                            "identifier": None,
                            "rationale": "Reviewed source",
                        },
                        idoc,
                    ),
                ),
            ]:
                row = service.review(session, access, sid, Review.model_validate(data), uuid4())
                approvals.append(row.id)
            pinned = [r.id for r in service.pinned_inputs(session, access, invoice)]
            session.commit()
        yield engine, access, cid, iid, cdoc, idoc, approvals, pinned
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin.dispose()


@pytest.mark.parametrize("same_request", [False, True])
def test_simultaneous_identical_evaluations_create_one_semantic_finding(
    financial_database, same_request
):
    engine, access, cid, iid, cdoc, idoc, approvals, pinned = financial_database
    barrier = Barrier(2)
    request = Evaluate(scope_key="line-1", expected_revisions=tuple(pinned))

    def start():
        with Session(engine) as session:
            barrier.wait(timeout=5)
            row = service.evaluate_scope(
                session,
                access,
                iid,
                request if same_request else Evaluate.model_validate(request.model_dump()),
            )
            result = row.id
            session.commit()
            return result

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: start(), range(2)))
    assert results[0] == results[1]
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(FinancialEvaluation)) == 1
        assert (
            session.scalar(
                select(func.count())
                .select_from(FinancialAudit)
                .where(FinancialAudit.action == "evaluation.created")
            )
            == 1
        )


@pytest.mark.parametrize(
    "change", ["fact_correction", "fact_revocation", "packet_revision", "association_revocation"]
)
def test_evaluation_and_material_revision_do_not_mix_inputs(financial_database, change):
    engine, access, cid, iid, cdoc, idoc, approvals, pinned = financial_database
    if change.startswith("fact"):
        data = body(
            "term",
            term(rate="10" if change == "fact_revocation" else "11"),
            cdoc,
            str(approvals[0]),
            "revoked" if change == "fact_revocation" else "approved",
        )
        sid = cid
    elif change == "packet_revision":
        data = body(
            "packet",
            packet(
                documents=({"document_id": cdoc, "role": "master"},),
                known_missing=("new schedule",),
            ),
            cdoc,
            str(approvals[1]),
        )
        sid = cid
    else:
        data = body(
            "association",
            {
                "contract_source_id": str(cid),
                "method": "manual",
                "identifier": None,
                "rationale": "Reviewed source",
            },
            idoc,
            str(approvals[3]),
            "revoked",
        )
        sid = iid
    entered = Event()

    def revise():
        with Session(engine) as session:
            entered.set()
            row = service.review(session, access, sid, Review.model_validate(data), uuid4())
            result = row.id
            session.commit()
            return result

    with Session(engine) as evaluating, ThreadPoolExecutor(max_workers=1) as pool:
        row = service.evaluate_scope(
            evaluating, access, iid, Evaluate(scope_key="line-1", expected_revisions=tuple(pinned))
        )
        original_id = row.id
        future = pool.submit(revise)
        assert entered.wait(timeout=5)
        # The material write cannot commit while the evaluated revision set is locked.
        assert not future.done()
        evaluating.commit()
        new_revision = future.result(timeout=10)
    with Session(engine) as session:
        original = session.get(FinancialEvaluation, original_id)
        assert original.potential == 200 and service.is_stale(session, access, original)
        assert new_revision not in {UUID(r["id"]) for r in original.snapshot["inputs"]}
        with pytest.raises(HTTPException) as stale:
            service.evaluate_scope(
                session, access, iid, Evaluate(scope_key="line-1", expected_revisions=tuple(pinned))
            )
        assert stale.value.detail["code"] == "STALE_INPUT"


def test_concurrent_approval_and_revocation_require_one_current_predecessor(financial_database):
    engine, access, cid, iid, cdoc, idoc, approvals, pinned = financial_database
    barrier = Barrier(2)

    def decide(state):
        with Session(engine) as session:
            barrier.wait(timeout=5)
            data = body(
                "term",
                term(rate="10" if state == "revoked" else "11"),
                cdoc,
                str(approvals[0]),
                state,
            )
            try:
                row = service.review(session, access, cid, Review.model_validate(data), uuid4())
                session.commit()
                return row.state
            except HTTPException as exc:
                session.rollback()
                return exc.detail["code"]

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(decide, ["approved", "revoked"]))
    assert results.count("STALE_INPUT") == 1
    assert len([r for r in results if r in {"approved", "revoked"}]) == 1


def test_simultaneous_review_retry_preserves_source_and_revision_identity(financial_database):
    engine, access, cid, iid, cdoc, idoc, approvals, pinned = financial_database
    barrier = Barrier(2)
    key = uuid4()
    data = Review.model_validate(body("term", term(rate="11"), cdoc, str(approvals[0])))

    def submit():
        with Session(engine) as session:
            barrier.wait(timeout=5)
            row = service.review(session, access, cid, data, key)
            result = row.id
            session.commit()
            return result

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: submit(), range(2)))
    assert results[0] == results[1]
