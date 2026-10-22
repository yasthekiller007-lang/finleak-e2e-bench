import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, delete, func, select
from sqlalchemy.orm import Session

from app.auth.dependencies import resolve_user
from app.auth.oidc import VerifiedIdentity
from app.db.models import User, UserIdentity

pytestmark = pytest.mark.integration


def test_simultaneous_first_logins_create_one_user_without_orphan_identity():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set isolated TEST_DATABASE_URL")
    engine = create_engine(url, connect_args={"options": "-c statement_timeout=5000"})
    issuer = "https://concurrent-" + uuid4().hex + ".example.test"
    email = uuid4().hex + "@fixture.example.test"
    identity = VerifiedIdentity(issuer, "shared-subject", email)
    barrier = Barrier(2)

    class RacingSession(Session):
        first_read = True

        def scalar(self, *args, **kwargs):
            result = super().scalar(*args, **kwargs)
            if self.first_read:
                self.first_read = False
                assert result is None
                barrier.wait(timeout=5)
            return result

    def login():
        with RacingSession(engine) as session:
            return resolve_user(session, identity).id

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            users = list(pool.map(lambda _: login(), range(2)))
        assert users[0] == users[1]
        with Session(engine) as session:
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(UserIdentity)
                    .where(UserIdentity.issuer == issuer)
                )
                == 1
            )
            assert (
                session.scalar(select(func.count()).select_from(User).where(User.email == email))
                == 1
            )
    finally:
        with Session(engine) as session, session.begin():
            session.execute(delete(UserIdentity).where(UserIdentity.issuer == issuer))
            session.execute(delete(User).where(User.email == email))
        engine.dispose()
