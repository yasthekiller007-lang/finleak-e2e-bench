"""Deterministic assembly from frozen records. No matching, compilation or calculation."""

from copy import deepcopy
from datetime import datetime
from decimal import Decimal

from app.financial.engine import fingerprint as financial_fingerprint
from app.financial.service import inputs_snapshot
from app.proof.budget import Budget, ProofError
from app.proof.canonical import (
    ASSEMBLY,
    DECIMAL,
    SCHEMA,
    CanonicalError,
    canonical,
    digest,
    leaves,
    snapshot_digest,
)

KINDS = {
    "POTENTIAL_LEAKAGE": "MONETARY_FINDING_PROOF",
    "NO_OVERCHARGE": "ASSESSED_COMPARISON_EVIDENCE",
    "UNDERCHARGE": "ASSESSED_COMPARISON_EVIDENCE",
    "NEEDS_REVIEW": "BLOCKED_ASSESSMENT_EVIDENCE",
}
VERSIONS = {
    "schema": "financial-snapshot/1",
    "compiler": "reviewed-compiler/1",
    "rules": "core-bundle/1",
}
AMOUNTS = {
    "posted_amount",
    "billed_gross",
    "billed_discount",
    "contractual_gross",
    "amount",
    "quantum",
}


def integrity(message="Historical evidence records disagree"):
    raise ProofError("proof_integrity_failure", message)


def typed(value, pointer, record):
    name = pointer.rsplit("/", 1)[-1]
    body = record["payload"]["value"]
    currency, unit = body.get("currency"), body.get("unit")
    result = {"value": value, "type": "null" if value is None else "identity"}
    if value is None:
        return result
    if name in AMOUNTS | {"rate", "billed_rate", "percentage", "quantity"}:
        if not isinstance(value, str) or not DECIMAL.fullmatch(value):
            integrity("A financial input is not an exact decimal string")
        if name == "quantity":
            result.update(type="quantity", unit=unit)
        elif name == "percentage":
            result.update(
                type="percentage",
                base=body.get("discount_base"),
                eligible_members=body.get("eligible_members"),
                unconditional=body.get("unconditional"),
            )
        elif name == "quantum":
            result.update(type="rounding_quantum", currency=currency)
        elif name == "billed_rate" or (name == "rate" and body.get("family") == "unit_price"):
            result.update(type="unit_price", currency=currency, denominator=unit)
        else:
            result.update(type="money", currency=currency, tax_basis=body.get("tax_basis"))
    elif type(value) is bool:
        result["type"] = "boolean"
    elif name in {
        "effective_from",
        "effective_to",
        "service_from",
        "service_to",
        "invoice_date",
        "event_date",
    }:
        result.update(type="date", interval="start-inclusive/end-exclusive")
    return result


def _assemble(
    evaluation, revisions, evidences, documents, runs, fields, audits, observations, budget: Budget
):
    """Arguments are one tenant's locked historical captures, not current heads."""
    snapshot = evaluation.snapshot
    canonical(snapshot)
    kind = KINDS.get(evaluation.outcome)
    if kind is None:
        integrity("Unsupported historical assessment outcome")
    monetary = evaluation.outcome != "NEEDS_REVIEW"
    checks = {f"C{i:02}": {"passed": True, "gaps": []} for i in range(1, 11)}
    gaps, limitations, bindings, normalized = [], [], [], []

    def gap(code, binding, message):
        entry = {"code": code, "binding": binding, "message": message}
        checks[code]["passed"] = False
        checks[code]["gaps"].append(entry)
        gaps.append(entry)

    if (
        snapshot.get("organization_id") != str(evaluation.organization_id)
        or snapshot.get("invoice_source_id") != str(evaluation.invoice_source_id)
        or snapshot.get("scope_key") != evaluation.scope_key
    ):
        integrity("Evaluation identity disagrees with its frozen snapshot")
    ids = snapshot.get("calculation_driving_revision_ids")
    if not isinstance(ids, list) or len(ids) != len(set(ids)):
        integrity("Invalid pinned revision set")
    budget.bound(len(ids), "revisions")
    pinned = {item["id"]: item for item in snapshot.get("inputs", [])}
    if len(pinned) != len(snapshot.get("inputs", [])) or not set(ids) <= pinned.keys():
        integrity("Pinned calculation input is missing from the snapshot")
    if all(snapshot.get(key) == version for key, version in VERSIONS.items()):
        semantic = {
            key: snapshot[key]
            for key in (
                "schema",
                "compiler",
                "rules",
                "invoice_source_id",
                "organization_id",
                "scope_key",
            )
        }
        semantic["inputs"] = [pinned[identity] for identity in ids]
        if financial_fingerprint(semantic) != evaluation.fingerprint:
            integrity("Financial fingerprint disagrees with its frozen driving inputs")
    stored = {str(row.id): row for row in revisions}
    docs = {str(row.id): row for row in documents}
    run_map = {str(row.id): row for row in runs}
    field_map = {str(row.id): row for row in fields}
    evidence_map = {}
    for row in evidences:
        evidence_map.setdefault(str(row.revision_id), []).append(row)
    audit_map = {}
    for row in audits:
        audit_map.setdefault(str(row.target_id), []).append(row)
    sources = {}
    authority = []

    def source(doc_id, expected_hash):
        doc = docs.get(doc_id)
        if doc and doc.sha256 != expected_hash:
            integrity("Pinned source metadata no longer matches")
        if doc_id in sources and sources[doc_id]["sha256"] != expected_hash:
            integrity("Conflicting historical source hashes")
        status = observations.get(doc_id, "UNCHECKED")
        if status == "MISMATCH":
            integrity("Original source bytes do not match their pinned hash")
        if status != "AVAILABLE_VERIFIED":
            gap("C07", doc_id, "Pinned original bytes were unavailable or not verified at issuance")
        sources[doc_id] = {
            "document_id": doc_id,
            "sha256": expected_hash,
            "size_bytes": doc.file_size if doc else None,
            "document_type": doc.document_type.value if doc else None,
            "verified_at_issuance": status == "AVAILABLE_VERIFIED",
        }

    for revision_id in sorted(ids):
        budget.check()
        record = pinned[revision_id]
        row = stored.get(revision_id)
        if row is None:
            gap("C03", revision_id, "Pinned revision is unavailable")
        elif inputs_snapshot([row])[0] != record:
            integrity("Pinned revision disagrees with its immutable snapshot")
        if row and row.organization_id != evaluation.organization_id:
            integrity()
        historical_audits = audit_map.get(revision_id, [])
        if any(e.detail not in record["provenance"] for e in evidence_map.get(revision_id, [])):
            integrity("Normalized evidence contains a conflicting historical binding")
        review_audit = next(
            (
                a
                for a in historical_audits
                if a.action == f"review.{record['kind']}.{record['state']}"
            ),
            None,
        )
        if not review_audit:
            gap("C04", revision_id, "Historical review audit is unavailable")
        elif str(review_audit.actor_id) != record["actor_id"] or (
            record["state"] == "approved"
            and review_audit.detail.get("role_at_action") not in {"owner", "admin"}
        ):
            integrity("Historical approval authority disagrees")
        if not record["payload"].get("reason") or not record.get("knowledge_cutoff"):
            gap("C04", revision_id, "Historical review rationale or cutoff is unavailable")
        authority.append(
            {
                "revision": deepcopy(record),
                "role": "approved_input" if record["state"] == "approved" else "blocking_guard",
                "audit_id": str(review_audit.id) if review_audit else None,
                "authority_role_at_action": review_audit.detail.get("role_at_action")
                if review_audit
                else None,
            }
        )
        supported = set()
        values = leaves(record["payload"]["value"])
        for detail in record["provenance"]:
            doc_id = detail["document_id"]
            source(doc_id, detail["sha256"])
            matching = [e for e in evidence_map.get(revision_id, []) if e.detail == detail]
            if len(matching) > 1:
                integrity("Duplicate normalized historical evidence identity")
            evidence = matching[0] if matching else None
            if evidence is None:
                gap("C09", revision_id, "Normalized historical evidence is unavailable")
            elif (
                str(evidence.document_id) != doc_id
                or (str(evidence.run_id) if evidence.run_id else None) != detail.get("run_id")
                or (str(evidence.field_id) if evidence.field_id else None) != detail.get("field_id")
            ):
                integrity("Normalized evidence lineage disagrees with provenance")
            run_id, field_id = detail.get("run_id"), detail.get("field_id")
            if not detail.get("manual"):
                run, field = run_map.get(run_id), field_map.get(field_id)
                if run is None or field is None:
                    gap("C09", field_id or revision_id, "Pinned extraction lineage is unavailable")
                elif (
                    run.document_sha256 != detail["sha256"]
                    or str(run.document_id) != doc_id
                    or str(field.document_id) != doc_id
                    or str(field.extraction_run_id) != run_id
                    or field.raw_value != detail["raw_value"]
                    or field.normalized_value != detail["normalized_candidate"]
                    or field.source != detail["source_location"]
                    or field.path != detail["field_path"]
                    or run.version_number != detail["run_version"]
                    or run.parser_version != detail["parser_version"]
                    or run.extractor_version != detail["extractor_version"]
                    or run.schema_version != detail["schema_version"]
                    or field.confidence != detail["confidence"]
                    or field.reason != detail["uncertainty"]
                ):
                    integrity("Pinned extraction values or behavior versions disagree")
            elif run_id or field_id:
                integrity("Manual evidence cannot claim extraction lineage")
            else:
                limitations.append("Manual reviewer citations are not machine-verified quotations.")
            if not detail.get("location") or not detail.get("quote"):
                gap("C03", revision_id, "Evidence citation is unresolved")
            for pointer in detail["supports"]:
                if pointer not in values:
                    integrity("Evidence support pointer is not a historical input")
                supported.add(pointer)
                binding_id = (
                    str(evidence.id)
                    if evidence
                    else digest(
                        "FLA-PROOF-BINDING/1",
                        [
                            revision_id,
                            pointer,
                            doc_id,
                            detail["sha256"],
                            run_id,
                            field_id,
                            pointer,
                            detail.get("source_location"),
                        ],
                    )
                )
                binding = {
                    "binding_id": binding_id,
                    "revision_id": revision_id,
                    "input_pointer": pointer,
                    "evidence_id": str(evidence.id) if evidence else None,
                    "role": "approved_input" if record["state"] == "approved" else "blocking_guard",
                    "typed_input": typed(values[pointer], pointer, record),
                    "source": deepcopy(detail),
                    "location_precision": "reviewer_citation"
                    if detail["manual"]
                    else "recorded_extraction",
                }
                bindings.append(binding)
                if evidence:
                    normalized.append((evidence, binding))
                budget.bound(len(bindings), "bindings")
        for pointer in sorted(values.keys() - supported):
            gap("C03", revision_id + pointer, "Historical reviewed input has no evidence support")
        for doc in record["payload"].get("document_hashes", []):
            source(doc["document_id"], doc["sha256"])
        if record["kind"] == "packet":
            hashed = {d["document_id"] for d in record["payload"].get("document_hashes", [])}
            for doc in record["payload"]["value"]["documents"]:
                if doc["document_id"] not in hashed:
                    gap("C05", revision_id, "Governing packet source hash is unavailable")

    budget.bound(len(sources), "documents")
    evaluation_audit = next(
        (a for a in audit_map.get(str(evaluation.id), []) if a.action == "evaluation.created"), None
    )
    if not evaluation_audit:
        gap("C10", str(evaluation.id), "Financial evaluation audit is unavailable")
    elif evaluation_audit.actor_id != evaluation.actor_id:
        integrity("Evaluation audit actor disagrees")
    for key, expected in VERSIONS.items():
        if snapshot.get(key) != expected:
            gap(
                "C10",
                key,
                "Historical financial behavior version is not supported by this assembler",
            )
    calculation = deepcopy(snapshot.get("calculation"))
    if monetary:
        if not calculation or not all(
            k in calculation
            for k in (
                "formula",
                "expected_raw",
                "actual_bridge_raw",
                "alternatives",
                "precision",
                "rules",
                "economic_dates",
            )
        ):
            gap("C06", str(evaluation.id), "Historical calculation trace is incomplete")
        selected = calculation.get("economic_dates", {}) if calculation else {}
        selected_rows = [
            r
            for r in authority
            if r["revision"]["kind"] == "term" and r["revision"]["key"] in selected
        ]
        if len(selected_rows) != len(selected) or any(
            r["revision"]["state"] != "approved" for r in selected_rows
        ):
            gap(
                "C04",
                str(evaluation.id),
                "Selected contractual terms lack approved historical authority",
            )
        for required_kind in ("billing_scope", "association", "packet"):
            if not any(
                r["revision"]["kind"] == required_kind and r["revision"]["state"] == "approved"
                for r in authority
            ):
                gap(
                    "C05", required_kind, "Assessed comparison lacks historical governing authority"
                )
    elif any(
        getattr(evaluation, k) is not None
        for k in ("expected", "actual", "discrepancy", "potential")
    ):
        integrity("Blocked assessment has settled monetary outputs")
    if calculation and "alternatives" in calculation:
        calculation["alternatives"] = sorted(calculation["alternatives"], key=lambda a: a["mode"])
    for pointer, value in leaves(calculation).items():
        if pointer.rsplit("/", 1)[-1] in {
            "expected",
            "actual",
            "discrepancy",
            "expected_raw",
            "actual_bridge_raw",
        }:
            if value is not None and (not isinstance(value, str) or not DECIMAL.fullmatch(value)):
                integrity("Recorded arithmetic is not an exact decimal string")
    if monetary and calculation and calculation.get("alternatives"):
        for key in ("expected", "actual", "discrepancy"):
            values = {Decimal(item[key]) for item in calculation["alternatives"]}
            recorded = getattr(evaluation, key)
            if (recorded is None and len(values) == 1) or (
                recorded is not None and values != {recorded}
            ):
                integrity("Settled outputs disagree with the recorded rounding alternatives")
    limitations.extend(
        [
            "Evidence completeness is not legal certification, financial confirmation or recovery.",
            "Unrecorded arithmetic intermediates remain not recorded; "
            "independent reconstruction is verification only.",
            snapshot.get("coverage", "Only the named historical billing scope is assessed."),
        ]
    )
    if calculation and calculation.get("invariant"):
        limitations.append(
            "Rounding alternatives remain unresolved; the recorded discrepancy is invariant."
        )
    financial = {
        "outcome": evaluation.outcome,
        "reason_code": evaluation.reason_code,
        "explanation": evaluation.explanation,
        "currency": evaluation.currency,
        "evaluation_actor_id": str(evaluation.actor_id),
        "evaluated_at": evaluation.created_at.isoformat(),
        **{
            key: format(getattr(evaluation, key), "f")
            if getattr(evaluation, key) is not None
            else None
            for key in ("expected", "actual", "discrepancy", "potential")
        },
    }
    records = [a["revision"] for a in authority]
    core = {
        "schema": SCHEMA,
        "assembly": ASSEMBLY,
        "canonical_profile": "proof-canonical/1",
        "identity": {
            "organization_id": str(evaluation.organization_id),
            "evaluation_id": str(evaluation.id),
            "evaluation_fingerprint": evaluation.fingerprint,
            "finding_id": str(evaluation.id) if evaluation.outcome == "POTENTIAL_LEAKAGE" else None,
            "kind": kind,
            "invoice_source_id": str(evaluation.invoice_source_id),
            "scope_key": evaluation.scope_key,
            "members": (snapshot.get("billing_scope") or {}).get("members"),
        },
        "financial": financial,
        "behavior": {key: snapshot.get(key) for key in VERSIONS},
        "authority": authority,
        "governing": [r for r in records if r["kind"] in {"packet", "term"}],
        "billing": {
            "scope": deepcopy(snapshot.get("billing_scope")),
            "guards": [r for r in records if r["kind"] == "billing_scope"],
        },
        "matching": {
            "outcome": snapshot.get("match_outcome"),
            "records": [r for r in records if r["kind"] in {"association", "reference"}],
        },
        "calculation": {
            "recorded_trace": calculation,
            "bindings": sorted(
                bindings, key=lambda b: (b["revision_id"], b["input_pointer"], b["binding_id"])
            ),
        },
        "sources": sorted(sources.values(), key=lambda d: (d["document_id"], d["sha256"])),
        "completeness": {
            "version": "proof-completeness/1",
            "state": "INCOMPLETE" if gaps else "COMPLETE",
            "requirements": checks,
            "gaps": sorted(gaps, key=lambda g: (g["code"], g["binding"] or "")),
        },
        "limitations": sorted(set(limitations)),
        "evaluation_snapshot_digest": snapshot_digest(snapshot),
    }
    # Every C01–C10 result describes a concrete automated invariant above. C02 copies exact
    # immutable outputs; C08 retains blocker, source uncertainty and invariance, never a score.
    budget.bound(len(canonical(core)), "canonical_bytes")
    return core, normalized


def assemble(*args, **kwargs):
    try:
        return _assemble(*args, **kwargs)
    except (CanonicalError, KeyError, TypeError, ValueError, RecursionError) as exc:
        raise ProofError("proof_snapshot_integrity", "Historical proof inputs are invalid") from exc


def observation_time():
    from datetime import UTC

    return datetime.now(UTC).isoformat()
