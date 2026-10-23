"""D2 producer: categorize real exception types; never format private errors."""

import re

import psycopg
from sqlalchemy.exc import DBAPIError, IntegrityError, SQLAlchemyError

from acceptance.p0_diagnostics import SEED_STAGE, validate_d2


def postgres_sqlstate(error):
    """Bounded, cycle-safe traversal; only an actual psycopg error supplies state."""
    pending, seen = [error], set()
    for _ in range(8):
        if not pending:
            break
        current = pending.pop(0)
        if not isinstance(current, BaseException) or id(current) in seen:
            continue
        seen.add(id(current))
        if isinstance(current, psycopg.Error):
            try:
                state = current.sqlstate
            except Exception:
                state = None
            if isinstance(state, str) and re.fullmatch(r"[0-9A-Z]{5}", state) and state != "00000":
                return state
        if isinstance(current, SQLAlchemyError):
            pending.append(getattr(current, "orig", None))
        pending.extend((current.__cause__, current.__context__))
    return None


def failure_detail(error, reason_code, phase, substage, *, fixture_status="BLOCKED"):
    if isinstance(error, IntegrityError):
        category = "sqlalchemy_integrity"
    elif isinstance(error, DBAPIError):
        category = "sqlalchemy_database"
    elif isinstance(error, SQLAlchemyError):
        category = "sqlalchemy_orm"
    elif isinstance(error, psycopg.Error):
        category = "postgresql"
    elif isinstance(error, AssertionError):
        category = "assertion"
    elif isinstance(error, ValueError) and substage == "operator_context":
        category = "operator_rejected"
    elif isinstance(error, TimeoutError):
        category = "timeout"
    elif isinstance(error, OSError):
        category = "filesystem"
    else:
        category = "unexpected"
    # A wrapped driver error can supply a state, but an unrelated category cannot
    # imply that the top-level failure was a PostgreSQL operation.
    sqlstate = (
        postgres_sqlstate(error)
        if category
        in {"sqlalchemy_integrity", "sqlalchemy_database", "sqlalchemy_orm", "postgresql"}
        else None
    )
    value = {
        "schema_version": 2,
        "stage": SEED_STAGE,
        "substage": substage,
        "fixture_status": fixture_status,
        "reason_code": reason_code,
        "exception_category": category,
        "sqlstate": sqlstate,
        "e2e_executed": False,
    }
    validate_d2(value, reason_code=reason_code, phase=phase, fixture_status=fixture_status)
    return value
