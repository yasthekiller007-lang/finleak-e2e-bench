"""Read-only, bounded original reconciliation for protected incident/restore operators."""

import argparse
import hashlib
import json
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import Document
from app.db.session import create_database_engine
from app.modules.storage import build_storage
from app.proof.budget import Budget, ProofError, verify_source
from app.proof.schema import OperationalLimits


def reconcile_originals(
    storage, documents, *, max_documents=100, source_bytes=100 * 1024 * 1024, work_seconds=25
):
    """All supplied originals must verify; partial work is never a successful inventory.

    The caller pins PostgreSQL metadata. Raw private storage is used intentionally so
    operational reconciliation can inspect quarantined evidence without releasing it.
    No byte, original filename, quotation, financial amount or credential is exported.
    """
    if not 1 <= max_documents <= 1000 or not 1 <= source_bytes <= 100 * 1024 * 1024:
        raise ValueError("Invalid reconciliation bounds")
    if not 1 <= work_seconds <= 25:
        raise ValueError("Invalid reconciliation work bound")
    documents = list(documents)
    if len(documents) > max_documents:
        return {"result": "INCOMPLETE", "reason": "inventory_document_limit", "items": []}
    budget = Budget(OperationalLimits(source_bytes=source_bytes, work_seconds=work_seconds))
    records = []
    for document in documents:
        try:
            status, _ = verify_source(storage, document, budget)
        except ProofError as error:
            return {"result": "INCOMPLETE", "reason": error.code, "items": records}
        records.append(
            {
                "organization_id": str(document.organization_id),
                "document_id": str(document.id),
                "expected_sha256": document.sha256,
                "expected_size": document.file_size,
                "status": status,
            }
        )
    canonical = json.dumps(records, sort_keys=True, separators=(",", ":")).encode()
    return {
        "result": "PASS" if all(r["status"] == "AVAILABLE_VERIFIED" for r in records) else "FAIL",
        "document_count": len(documents),
        "bytes_read": budget.bytes_read,
        "inventory_sha256": hashlib.sha256(b"fla-original-inventory-v1\0" + canonical).hexdigest(),
        "items": records,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--organization", type=UUID, required=True)
    parser.add_argument("--max-documents", type=int, default=100)
    args = parser.parse_args()
    if not 1 <= args.max_documents <= 1000:
        parser.error("max-documents must be between 1 and 1000")
    settings = Settings()
    engine = create_database_engine(settings)
    if engine is None:
        raise SystemExit("inventory_database_required")
    try:
        with engine.connect().execution_options(isolation_level="REPEATABLE READ") as connection:
            with connection.begin(), Session(connection) as session:
                session.execute(text("SET TRANSACTION READ ONLY"))
                documents = session.scalars(
                    select(Document)
                    .where(Document.organization_id == args.organization)
                    .order_by(Document.id)
                    .limit(args.max_documents + 1)
                ).all()
                result = reconcile_originals(
                    build_storage(settings), documents, max_documents=args.max_documents
                )
        print(json.dumps(result, sort_keys=True))
        if result["result"] != "PASS":
            raise SystemExit(1)
    except SystemExit:
        raise
    except Exception:
        raise SystemExit("inventory_unavailable") from None
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
