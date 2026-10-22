"""Explicit, credential-free PostgreSQL role foundation for a future runtime."""

import argparse
import re
from dataclasses import dataclass

from sqlalchemy import Connection, text

from app.core.config import Settings
from app.db.session import create_database_engine


@dataclass(frozen=True)
class Roles:
    application: str = "fla_app"
    migration: str = "fla_migration"
    operator: str = "fla_operator"
    scanner: str = "fla_scanner"

    def validate(self):
        names = (self.application, self.migration, self.operator, self.scanner)
        if len(set(names)) != 4 or any(
            not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", n)
            or n.startswith("pg_")
            or n in {"postgres", "public"}
            for n in names
        ):
            raise ValueError("Role names must be distinct safe dedicated group identifiers")


def bootstrap(connection: Connection, roles: Roles) -> None:
    """No passwords/logins, ownership reassignment, tenant grants or deployment."""
    roles.validate()
    quote = connection.dialect.identifier_preparer.quote_identifier
    for name in (roles.application, roles.migration, roles.operator, roles.scanner):
        row = connection.execute(
            text(
                "SELECT rolsuper,rolcreaterole,rolcreatedb,rolreplication,rolbypassrls,rolcanlogin "
                "FROM pg_roles WHERE rolname=:name"
            ),
            {"name": name},
        ).first()
        if row is None:
            connection.exec_driver_sql(
                f"CREATE ROLE {quote(name)} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
                "NOREPLICATION NOBYPASSRLS"
            )
        elif any(row):
            raise ValueError(
                "Existing runtime group has unsafe attributes; explicit review required"
            )
    database = quote(connection.scalar(text("SELECT current_database()")))
    connection.exec_driver_sql(f"REVOKE CREATE,TEMPORARY ON DATABASE {database} FROM PUBLIC")
    connection.exec_driver_sql("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
    for name in (roles.application, roles.migration, roles.operator, roles.scanner):
        connection.exec_driver_sql(f"GRANT CONNECT ON DATABASE {database} TO {quote(name)}")
        connection.exec_driver_sql(f"GRANT USAGE ON SCHEMA public TO {quote(name)}")
    connection.exec_driver_sql(f"GRANT CREATE ON SCHEMA public TO {quote(roles.migration)}")


APPLICATION_WRITABLE = {
    "users",
    "user_identities",
    "documents",
    "extraction_runs",
    "extracted_fields",
    "reviewed_financial_sources",
    "financial_revisions",
    "financial_evaluations",
    "financial_audit",
    "financial_finding_decisions",
    "financial_revision_evidence",
    "proof_families",
    "proof_packages",
    "proof_bindings",
    "proof_events",
    "proof_artifacts",
    "proof_requests",
    "proof_successors",
    "recovery_cases",
    "recovery_instruments",
    "recovery_proposals",
    "recovery_evidence",
    "recovery_records",
    "recovery_aliases",
    "recovery_requests",
    "recovery_publications",
}


def grant_runtime(connection: Connection, roles: Roles) -> None:
    roles.validate()
    quote = connection.dialect.identifier_preparer.quote_identifier
    application, operator, scanner = (
        quote(roles.application),
        quote(roles.operator),
        quote(roles.scanner),
    )
    tables = connection.scalars(
        text("SELECT tablename FROM pg_tables WHERE schemaname='public'")
    ).all()
    for table in tables:
        target = "public." + quote(table)
        # Re-run after every migration: future tables receive no default blanket authority.
        connection.exec_driver_sql(
            f"REVOKE ALL ON {target} FROM {application},{operator},{scanner}"
        )
        if table != "pilot_access_journal":
            connection.exec_driver_sql(f"GRANT SELECT ON {target} TO {application}")
        if table in {"pilot_intake_profiles", "pilot_intake_attempts"}:
            connection.exec_driver_sql(f"GRANT INSERT ON {target} TO {application}")
        if table in {"pilot_source_releases", "pilot_source_requests"}:
            connection.exec_driver_sql(f"GRANT INSERT ON {target} TO {application}")
        if table in {
            # Scanner readiness verifies the exact schema head before accepting work.
            # This metadata grant conveys no financial or migration write authority.
            "alembic_version",
            "users",
            "organizations",
            "organization_memberships",
            "documents",
            "pilot_user_access",
            "pilot_tenant_access",
            "pilot_source_scans",
            "pilot_source_releases",
            "pilot_source_requests",
        }:
            connection.exec_driver_sql(f"GRANT SELECT ON {target} TO {scanner}")
        if table in {"organizations", "documents", "organization_memberships"}:
            connection.exec_driver_sql(f"GRANT UPDATE(id) ON {target} TO {scanner}")
        if table in {"pilot_source_scans", "pilot_source_requests"}:
            connection.exec_driver_sql(f"GRANT INSERT ON {target} TO {scanner}")
        if table in APPLICATION_WRITABLE:
            privileges = "INSERT" if table in {"users", "user_identities"} else "INSERT,UPDATE"
            connection.exec_driver_sql(f"GRANT {privileges} ON {target} TO {application}")
        if table in {"organizations", "organization_memberships"}:
            # Existing tenant/membership FOR UPDATE fences require an UPDATE privilege.
            # Role/tenant/user/name columns remain unwritable by the application principal.
            connection.exec_driver_sql(f"GRANT UPDATE (id) ON {target} TO {application}")
        if table in {"users", "user_identities", "organizations", "organization_memberships"}:
            connection.exec_driver_sql(f"GRANT SELECT ON {target} TO {operator}")
        if table == "organizations":
            connection.exec_driver_sql(f"GRANT INSERT,UPDATE ON {target} TO {operator}")
        if table == "organization_memberships":
            connection.exec_driver_sql(f"GRANT INSERT,UPDATE,DELETE ON {target} TO {operator}")
        if table in {"pilot_user_access", "pilot_tenant_access", "pilot_access_journal"}:
            connection.exec_driver_sql(f"GRANT SELECT ON {target} TO {operator}")
        if table in {"pilot_user_access", "pilot_tenant_access"}:
            connection.exec_driver_sql(f"GRANT INSERT,UPDATE ON {target} TO {operator}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["bootstrap", "grant-runtime"])
    parser.add_argument("--apply", action="store_true", help="explicit privileged operator action")
    parser.add_argument("--application", default="fla_app")
    parser.add_argument("--migration", default="fla_migration")
    parser.add_argument("--operator", default="fla_operator")
    parser.add_argument("--scanner", default="fla_scanner")
    args = parser.parse_args()
    if not args.apply:
        parser.error(
            "No database change made; --apply requires an approved target/operator session"
        )
    roles = Roles(args.application, args.migration, args.operator, args.scanner)
    engine = create_database_engine(Settings())
    if engine is None:
        parser.error("Database is not configured")
    try:
        with engine.begin() as connection:
            (bootstrap if args.action == "bootstrap" else grant_runtime)(connection, roles)
        print("Role foundation applied; no login credential or tenant membership created")
    except Exception:
        parser.exit(1, "Role foundation failed; use protected operator diagnostics\n")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
