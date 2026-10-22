import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, delete, func, select
from sqlalchemy.orm import Session

from app.auth.dependencies import OrganizationAccess
from app.core.config import Settings
from app.db.models import Document, ExtractionRun, Organization, OrganizationMembership, User
from app.domain.types import DocumentType, MembershipRole, ProcessingStatus
from app.intelligence.service import claim

pytestmark = pytest.mark.integration


def test_simultaneous_processing_claims_create_one_audited_attempt():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set isolated TEST_DATABASE_URL")
    engine = create_engine(url, connect_args={"options": "-c statement_timeout=5000"})
    organization_id, user_id, document_id = uuid4(), uuid4(), uuid4()
    barrier = Barrier(2)
    access = OrganizationAccess(organization_id, user_id, MembershipRole.ANALYST)
    settings = Settings(_env_file=None, environment="test")
    try:
        with Session(engine) as session, session.begin():
            session.add(Organization(id=organization_id, name="Synthetic concurrent tenant"))
            session.add(User(id=user_id, display_name="Synthetic operator"))
            session.flush()
            session.add(
                OrganizationMembership(
                    organization_id=organization_id, user_id=user_id, role="analyst"
                )
            )
            session.add(
                Document(
                    id=document_id,
                    organization_id=organization_id,
                    original_filename="synthetic.csv",
                    mime_type="text/csv",
                    file_size=10,
                    storage_key=str(uuid4()),
                    sha256="a" * 64,
                    document_type=DocumentType.INVOICE,
                    processing_status=ProcessingStatus.PENDING,
                )
            )

        def start():
            with Session(engine) as session:
                barrier.wait(timeout=5)
                _, run, created = claim(session, access, document_id, uuid4(), settings)
                return run.id, created

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: start(), range(2)))
        assert results[0][0] == results[1][0]
        assert sorted(created for _, created in results) == [False, True]
        with Session(engine) as session:
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(ExtractionRun)
                    .where(ExtractionRun.document_id == document_id)
                )
                == 1
            )
    finally:
        with Session(engine) as session, session.begin():
            session.execute(delete(ExtractionRun).where(ExtractionRun.document_id == document_id))
            session.execute(delete(Document).where(Document.id == document_id))
            session.execute(
                delete(OrganizationMembership).where(
                    OrganizationMembership.organization_id == organization_id
                )
            )
            session.execute(delete(Organization).where(Organization.id == organization_id))
            session.execute(delete(User).where(User.id == user_id))
        engine.dispose()
