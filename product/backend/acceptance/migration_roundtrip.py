"""Empty-chain qualification uses a fresh disposable CI database, never audit erasure."""

import os
import subprocess
import sys
from uuid import uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


def main():
    if os.environ.get("FLA_ENVIRONMENT") != "test" or not os.environ.get("CI"):
        raise SystemExit("Disposable migration qualification is CI-only")
    original = make_url(os.environ["TEST_DATABASE_URL"])
    name = "phase7_roundtrip_" + uuid4().hex
    engine = create_engine(original, isolation_level="AUTOCOMMIT", hide_parameters=True)
    with engine.connect() as connection:
        connection.exec_driver_sql(f'CREATE DATABASE "{name}"')
    try:
        environment = dict(os.environ)
        environment["FLA_DATABASE_URL"] = original.set(database=name).render_as_string(
            hide_password=False
        )
        for command in (
            ("upgrade", "head"),
            ("check",),
            ("downgrade", "base"),
            ("upgrade", "head"),
            ("check",),
        ):
            subprocess.run(
                [sys.executable, "-m", "alembic", *command], env=environment, check=True, timeout=90
            )
        print("Empty migration chain, downgrade, re-upgrade and schema drift: PASS")
    finally:
        with engine.connect() as connection:
            connection.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
        engine.dispose()


if __name__ == "__main__":
    main()
