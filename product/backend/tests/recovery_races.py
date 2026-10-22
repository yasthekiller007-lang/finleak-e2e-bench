"""Independent PostgreSQL sessions for simultaneous recognition."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.auth.dependencies import OrganizationAccess
from app.domain.types import MembershipRole
from app.proof.budget import ProofError
from app.recovery import service
from app.recovery.schema import Approve


def access_for(api):
    return OrganizationAccess(api["orgs"]["a"], api["users"]["a"].id, MembershipRole.OWNER)


def approve_race(api, engine, proposals, same_key=False):
    access = access_for(api)
    head = proposals[0]["authority"]["head"]
    body = Approve(expected_head=head, reason="Independent concurrent financial review")
    storage, limits = api["app"].state.storage, api["app"].state.settings.recovery_limits
    api["session"].commit()  # Release fixture reader's share lock before independent writers.
    barrier = Barrier(len(proposals))
    shared_key = uuid4()

    def run(proposal):
        with Session(engine) as session:
            barrier.wait(timeout=10)
            try:
                result = service.execute(
                    session,
                    access,
                    "approve",
                    UUID(proposal["id"]),
                    body,
                    shared_key if same_key else uuid4(),
                    storage,
                    limits,
                )
                session.commit()
                return result
            except (HTTPException, ProofError) as exc:
                session.rollback()
                return {"error": {"code": getattr(exc, "code", "FORBIDDEN")}}

    with ThreadPoolExecutor(max_workers=len(proposals)) as pool:
        return list(pool.map(run, proposals))
