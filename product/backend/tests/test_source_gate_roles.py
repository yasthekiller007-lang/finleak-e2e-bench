from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.core.preflight import PRIVILEGE_QUERY, SCANNER_PRIVILEGE_QUERY
from app.operations.roles import Roles, bootstrap, grant_runtime
from tests.test_documents import api as api
from tests.test_documents import upload
from tests.test_financial_api import set_role

pytestmark = pytest.mark.integration


def test_application_cannot_forge_scan_and_scanner_cannot_release_or_write_money(api):
    set_role(api, "owner")
    response = upload(api, release=False)
    document = response.json()
    suffix = uuid4().hex[:12]
    roles = Roles("app_" + suffix, "migration_" + suffix, "operator_" + suffix, "scanner_" + suffix)
    bootstrap(api["session"].connection(), roles)
    grant_runtime(api["session"].connection(), roles)
    fields = {
        "org": api["orgs"]["a"],
        "doc": UUID(document["id"]),
        "actor": api["users"]["a"].id,
        "sha": document["sha256"],
        "size": document["file_size"],
    }
    statement = text(
        "INSERT INTO pilot_source_scans(id,organization_id,document_id,actor_id,"
        "request_key,sequence,sha256,file_size,actual_sha256,actual_file_size,"
        "verdict,scanner_profile,scanner_version,reason) VALUES(gen_random_uuid(),"
        ":org,:doc,:actor,gen_random_uuid(),1,:sha,:size,:sha,:size,'CLEAN',"
        "'private-clamav/1','clamav/1.4.6;database/28000','Protected synthetic scan')"
    )
    with api["session"].begin_nested() as point:
        api["session"].execute(text(f'SET LOCAL ROLE "{roles.application}"'))
        assert api["session"].scalar(text(PRIVILEGE_QUERY)) is False
        with pytest.raises(DBAPIError, match="permission denied"):
            with api["session"].begin_nested():
                api["session"].execute(statement, fields)
        point.rollback()
    with api["session"].begin_nested() as point:
        api["session"].execute(text(f'SET LOCAL ROLE "{roles.scanner}"'))
        assert api["session"].scalar(text(SCANNER_PRIVILEGE_QUERY)) is False
        api["session"].execute(statement, fields)
        for forbidden in (
            "INSERT INTO pilot_source_releases DEFAULT VALUES",
            "INSERT INTO financial_revisions DEFAULT VALUES",
            "INSERT INTO financial_evaluations DEFAULT VALUES",
            "INSERT INTO proof_packages DEFAULT VALUES",
            "INSERT INTO recovery_records DEFAULT VALUES",
            "UPDATE organization_memberships SET role='owner'",
            "TRUNCATE pilot_source_scans",
        ):
            with pytest.raises(DBAPIError, match="permission denied"):
                with api["session"].begin_nested():
                    api["session"].execute(text(forbidden))
        point.rollback()
