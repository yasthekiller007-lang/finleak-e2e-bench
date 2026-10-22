"""Independent READ ONLY PostgreSQL witness. Never inserts a financial result."""

import argparse
import json
import os
from pathlib import Path
from uuid import UUID

from acceptance.product_v11 import engine, guard
from app.financial.models import (
    FinancialAudit,
    FinancialEvaluation,
    FinancialFindingDecision,
)
from app.proof.models import ProofPackage
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[2]


def read(evaluation, decision, package, count):
    if (
        guard()
        or os.getenv("P0_EXECUTION") != "1"
        or os.getenv("GITHUB_ACTIONS") != "true"
    ):
        raise ValueError("Authorized isolated synthetic witness required")
    roster = json.loads((ROOT / ".local/product-v11/roster.json").read_text())
    organization = UUID(roster["organization"])
    db = engine()
    try:
        with Session(db) as session:
            session.execute(text("SET TRANSACTION READ ONLY"))
            version = int(session.scalar(text("SHOW server_version_num")))
            assert 170000 <= version < 180000
            elevated = session.scalar(
                text(
                    "SELECT rolsuper OR rolcreaterole OR rolcreatedb "
                    "FROM pg_roles WHERE rolname=current_user"
                )
            )
            assert not elevated
            owner = session.scalar(
                text(
                    "SELECT pg_get_userbyid(datdba)=current_user FROM pg_database WHERE datname=current_database()"
                )
            )
            assert not owner
            assert (
                session.scalar(text("SELECT version_num FROM alembic_version"))
                == "0010"
            )
            row = session.scalar(
                select(FinancialEvaluation).where(
                    FinancialEvaluation.organization_id == organization,
                    FinancialEvaluation.id == evaluation,
                )
            )
            assert row is not None and str(row.expected) == "5000.000000"
            assert (
                str(row.actual) == "6000.000000" and str(row.potential) == "1000.000000"
            )
            assert row.currency == "USD"
            decisions = session.scalars(
                select(FinancialFindingDecision)
                .where(
                    FinancialFindingDecision.organization_id == organization,
                    FinancialFindingDecision.evaluation_id == evaluation,
                )
                .order_by(FinancialFindingDecision.number)
            ).all()
            assert len(decisions) == count and [r.number for r in decisions] == list(
                range(1, count + 1)
            )
            assert decisions[0].id == decision and decisions[0].status == "confirmed"
            assert all(
                str(d.actor_id) == roster["owner"] and d.reason.strip()
                for d in decisions
            )
            audits = session.scalars(
                select(FinancialAudit).where(
                    FinancialAudit.organization_id == organization,
                    FinancialAudit.target_id.in_([d.id for d in decisions]),
                )
            ).all()
            assert len(audits) == count and all(
                a.action.startswith("finding.") for a in audits
            )
            proof = session.scalar(
                select(ProofPackage).where(
                    ProofPackage.organization_id == organization,
                    ProofPackage.id == package,
                )
            )
            assert proof is not None
            return {
                "status": "PASS",
                "fresh_database_session": True,
                "postgres_version_num": version,
                "superuser_createdb_createrole": False,
                "database_owner": False,
                "migration_head": "0010",
                "decision_rows": count,
                "audit_rows": len(audits),
                "first_decision_id": str(decision),
                "evaluation_id": str(evaluation),
                "proof_package_id": str(package),
                "expected": str(row.expected),
                "actual": str(row.actual),
                "potential": str(row.potential),
                "currency": "USD",
            }
    finally:
        db.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--evaluation", required=True, type=UUID)
    parser.add_argument("--decision", required=True, type=UUID)
    parser.add_argument("--package", required=True, type=UUID)
    parser.add_argument("--count", required=True, choices=(1, 2), type=int)
    args = parser.parse_args()
    try:
        print(
            json.dumps(read(args.evaluation, args.decision, args.package, args.count))
        )
    except (
        AssertionError,
        OSError,
        ValueError,
        KeyError,
        TypeError,
        SQLAlchemyError,
    ) as error:
        print(
            json.dumps(
                {
                    "status": "FAIL",
                    "check": "independent_postgresql_witness",
                    "error_type": type(error).__name__,
                }
            )
        )
        raise SystemExit(1) from None
