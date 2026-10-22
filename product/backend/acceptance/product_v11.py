"""Opt-in development fixture and read-only PostgreSQL witness, never an auth bypass.

No server, database, issuer, scanner or cloud resource is created. No financial
revision, evaluation or finding decision is inserted by this fixture.
"""

import argparse
import csv
import io
import json
import os
from pathlib import Path
from uuid import UUID, uuid4

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.auth.oidc import provider_json
from app.db.models import Document, Organization, OrganizationMembership, User, UserIdentity
from app.domain.types import DocumentType, ProcessingStatus
from app.financial.models import FinancialAudit, FinancialEvaluation, FinancialFindingDecision
from app.modules.storage import LocalObjectStorage, document_storage_key
from tests.financial_fixtures import bill, packet, term

BACKEND = Path(__file__).resolve().parents[1]
DIRECTORY = BACKEND.parent / ".local" / "product-v11"
DATABASE = "finleak_product_v11_test"


def scenario():
    return term(rate="50"), bill(
        quantity="100",
        billed_rate="60",
        posted_amount="6000",
        billed_gross="6000",
        label="DEMO 100 approved units",
    )


def source_material():
    ids = {kind: uuid4() for kind in ("contract", "invoice")}
    t, b = scenario()
    governing = packet(documents=({"document_id": ids["contract"], "role": "master"},))
    values = {
        "contract": {
            "term": t.model_dump(mode="json"),
            "packet": governing.model_dump(mode="json"),
        },
        "invoice": {
            "billing_scope": b.model_dump(mode="json"),
            "association_basis": {
                "contract_document_id": str(ids["contract"]),
                "method": "manual",
                "rationale": "DEMO explicitly reviewed invoice obligation",
            },
        },
    }
    originals = {}
    for kind, sections in values.items():
        output = io.StringIO(newline="")
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(["SYNTHETIC_SOURCE_SECTION", "SYNTHETIC_REVIEW_VALUE"])
        for name, value in sections.items():
            writer.writerow([name, json.dumps(value, sort_keys=True)])
        originals[kind] = output.getvalue().encode()
    return ids, originals, t, b, governing


def guard():
    """Fail before network/SQL. Secrets are never returned in diagnostics."""
    required = [
        "FLA_DATABASE_URL",
        "OIDC_ISSUER_URL",
        "PRODUCT_OWNER_SUBJECT",
        "PRODUCT_ANALYST_SUBJECT",
    ]
    missing = [name for name in required if not os.getenv(name)]
    if (
        os.getenv("PRODUCT_V11_ACCEPTANCE") != "1"
        or os.getenv("PRODUCT_SYNTHETIC_ACCOUNTS_ONLY") != "1"
        or os.getenv("FLA_ENVIRONMENT") != "test"
    ):
        missing.append("explicit_synthetic_development_authorization")
    if missing:
        return {"status": "BLOCKED", "missing": missing, "e2e": "NOT_EXECUTED"}
    try:
        url = make_url(os.environ["FLA_DATABASE_URL"])
        from urllib.parse import urlsplit

        issuer = urlsplit(os.environ["OIDC_ISSUER_URL"])
        if (
            url.drivername != "postgresql+psycopg"
            or url.host not in {"127.0.0.1", "localhost", "::1"}
            or url.database != DATABASE
        ):
            raise ValueError()
        if (
            issuer.hostname not in {"127.0.0.1", "localhost", "::1"}
            or issuer.scheme not in {"http", "https"}
            or issuer.username
            or issuer.password
            or issuer.query
            or issuer.fragment
        ):
            raise ValueError()
        if os.environ["PRODUCT_OWNER_SUBJECT"] == os.environ["PRODUCT_ANALYST_SUBJECT"]:
            raise ValueError()
    except Exception:
        return {
            "status": "BLOCKED",
            "missing": ["dedicated_loopback_database_and_test_issuer_configuration"],
            "e2e": "NOT_EXECUTED",
        }
    return None


def engine():
    return create_engine(
        os.environ["FLA_DATABASE_URL"],
        hide_parameters=True,
        connect_args={"connect_timeout": 5, "options": "-c timezone=UTC -c statement_timeout=5000"},
    )


def preflight():
    blocked = guard()
    if blocked:
        return blocked
    db = engine()
    try:
        with db.connect() as connection:
            version = int(connection.scalar(text("SHOW server_version_num")))
            if not 170000 <= version < 180000:
                return {"status": "BLOCKED", "missing": ["PostgreSQL_17"], "e2e": "NOT_EXECUTED"}
            elevated = connection.scalar(
                text(
                    "SELECT rolsuper OR rolcreaterole OR rolcreatedb "
                    "FROM pg_roles WHERE rolname = current_user"
                )
            )
            if elevated:
                return {
                    "status": "BLOCKED",
                    "missing": ["non_privileged_fixture_role"],
                    "e2e": "NOT_EXECUTED",
                }
            head = ScriptDirectory.from_config(
                Config(str(BACKEND / "alembic.ini"))
            ).get_current_head()
            if connection.scalar(text("SELECT version_num FROM alembic_version")) != head:
                return {
                    "status": "BLOCKED",
                    "missing": ["existing_migrations_at_head"],
                    "e2e": "NOT_EXECUTED",
                }
        issuer = os.environ["OIDC_ISSUER_URL"]
        metadata = provider_json(issuer.rstrip("/") + "/.well-known/openid-configuration", False)
        if (
            metadata.get("issuer") != issuer
            or "S256" not in metadata.get("code_challenge_methods_supported", [])
            or "RS256" not in metadata.get("id_token_signing_alg_values_supported", [])
        ):
            return {
                "status": "BLOCKED",
                "missing": ["test_OIDC_discovery_PKCE_RS256"],
                "e2e": "NOT_EXECUTED",
            }
        # Discovery reachability is not authentication.
        # The browser and backend must still validate tokens.
        return {
            "status": "PREFLIGHT_ONLY",
            "postgres_server_version_num": version,
            "migration_head": head,
            "oidc_discovery": "AVAILABLE_NOT_AUTHENTICATED",
            "e2e": "NOT_EXECUTED",
        }
    except Exception:
        return {
            "status": "BLOCKED",
            "missing": ["database_or_test_issuer_preflight"],
            "e2e": "NOT_EXECUTED",
        }
    finally:
        db.dispose()


def seed():
    result = preflight()
    if result["status"] != "PREFLIGHT_ONLY":
        return result
    db = engine()
    try:
        if (DIRECTORY / "roster.json").exists():
            return {
                "status": "BLOCKED",
                "missing": ["fresh_disposable_fixture_directory"],
                "e2e": "NOT_EXECUTED",
            }
        storage = LocalObjectStorage(DIRECTORY / "originals")
        with Session(db) as session, session.begin():
            if session.scalar(select(func.count()).select_from(Organization)) or session.scalar(
                select(func.count()).select_from(User)
            ):
                return {
                    "status": "BLOCKED",
                    "missing": ["empty_dedicated_test_database"],
                    "e2e": "NOT_EXECUTED",
                }
            company, other = (
                Organization(name="DEMO Product V1.1 Industries"),
                Organization(name="DEMO Inaccessible Tenant"),
            )
            owner, analyst = (
                User(display_name="DEMO Finance Owner", email=None),
                User(display_name="DEMO Financial Analyst", email=None),
            )
            session.add_all([company, other, owner, analyst])
            session.flush()
            for user, role, subject in [
                (owner, "owner", os.environ["PRODUCT_OWNER_SUBJECT"]),
                (analyst, "analyst", os.environ["PRODUCT_ANALYST_SUBJECT"]),
            ]:
                session.add(
                    UserIdentity(
                        user_id=user.id, issuer=os.environ["OIDC_ISSUER_URL"], subject=subject
                    )
                )
                session.add(
                    OrganizationMembership(organization_id=company.id, user_id=user.id, role=role)
                )
            docs = {}
            ids, originals, t, b, governing = source_material()
            for kind, data in originals.items():
                document_id = ids[kind]
                stored = storage.put(
                    document_storage_key(company.id, document_id), io.BytesIO(data), max_bytes=4096
                )
                session.add(
                    Document(
                        id=document_id,
                        organization_id=company.id,
                        original_filename=f"DEMO-ProductV11-{kind}.csv",
                        mime_type="text/csv",
                        file_size=stored.file_size,
                        storage_key=stored.key,
                        sha256=stored.sha256,
                        uploaded_by=owner.id,
                        document_type=DocumentType(kind),
                        processing_status=ProcessingStatus.NEEDS_REVIEW,
                    )
                )
                docs[kind] = str(document_id)
            roster = {
                "synthetic": True,
                "organization": str(company.id),
                "other_organization": str(other.id),
                "owner": str(owner.id),
                "analyst": str(analyst.id),
                "documents": docs,
                "quotes": {str(ids[kind]): data.decode() for kind, data in originals.items()},
                "term": t.model_dump(mode="json"),
                "billing": b.model_dump(mode="json"),
                "packet": governing.model_dump(mode="json"),
                "import_validation": "NOT_EXECUTED",
                "scanner": "BLOCKED",
            }
        DIRECTORY.mkdir(parents=True, exist_ok=True)
        (DIRECTORY / "roster.json").write_text(json.dumps(roster, indent=2) + "\n")
        return {
            "status": "FIXTURE_ONLY",
            "financial_records_inserted": 0,
            "roster": str(DIRECTORY / "roster.json"),
            "e2e": "NOT_EXECUTED",
        }
    finally:
        db.dispose()


def witness(evaluation_id, decision_id):
    blocked = guard()
    if blocked:
        return blocked
    roster = json.loads((DIRECTORY / "roster.json").read_text())
    db = engine()
    try:
        with Session(db) as session:
            session.execute(text("SET TRANSACTION READ ONLY"))
            assert 170000 <= int(session.scalar(text("SHOW server_version_num"))) < 180000
            rows = session.scalars(
                select(FinancialFindingDecision).where(
                    FinancialFindingDecision.organization_id == UUID(roster["organization"]),
                    FinancialFindingDecision.evaluation_id == evaluation_id,
                )
            ).all()
            decision = next((row for row in rows if row.id == decision_id), None)
            assert decision is not None
            evaluation = session.scalar(
                select(FinancialEvaluation).where(
                    FinancialEvaluation.id == evaluation_id,
                    FinancialEvaluation.organization_id == UUID(roster["organization"]),
                )
            )
            audit = session.scalar(
                select(FinancialAudit).where(
                    FinancialAudit.organization_id == UUID(roster["organization"]),
                    FinancialAudit.target_id == decision_id,
                    FinancialAudit.action == "finding.confirmed",
                )
            )
            assert (
                len(rows) == 1
                and decision.status == "confirmed"
                and str(decision.actor_id) == roster["owner"]
                and audit is not None
            )
            assert (
                str(evaluation.expected) == "5000.000000"
                and str(evaluation.actual) == "6000.000000"
                and str(evaluation.potential) == "1000.000000"
            )
            return {
                "status": "DATABASE_READ_PASS",
                "synthetic": True,
                "decision_id": str(decision.id),
                "evaluation_id": str(evaluation.id),
                "decision_rows": len(rows),
                "actor_id": str(decision.actor_id),
                "reason": decision.reason,
                "audit_id": str(audit.id),
                "expected": str(evaluation.expected),
                "actual": str(evaluation.actual),
                "potential": str(evaluation.potential),
                "currency": evaluation.currency,
                "fresh_database_session": True,
                "restart": "NOT_VERIFIED",
                "oidc_browser_session": "SEPARATE_EVIDENCE_REQUIRED",
            }
    finally:
        db.dispose()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["preflight", "seed", "witness"])
    parser.add_argument("--evaluation", type=UUID)
    parser.add_argument("--decision", type=UUID)
    args = parser.parse_args()
    try:
        if args.command == "preflight":
            result = preflight()
        elif args.command == "seed":
            result = seed()
        elif args.evaluation and args.decision:
            result = witness(args.evaluation, args.decision)
        else:
            result = {
                "status": "BLOCKED",
                "missing": ["synthetic_evaluation_and_decision_ids"],
                "e2e": "NOT_EXECUTED",
            }
    except AssertionError:
        result = {"status": "FAIL", "check": "persisted_financial_invariants"}
    except Exception:
        result = {
            "status": "BLOCKED",
            "missing": ["fixture_or_witness_verification_failed"],
            "e2e": "NOT_EXECUTED",
        }
    print(json.dumps(result, indent=2))
    return 2 if result["status"] == "BLOCKED" else 1 if result["status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
