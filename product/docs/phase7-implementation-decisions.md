# Phase 7 execution decisions

Recorded 4 October 2026. Starting main: `4a0d2520d4713355cec8b143f233aa61e5e655cc`, with Phase 6 implementation PR #11 merged. The user’s final consolidated Phase 7 instruction explicitly authorizes implementation on `phase7/pilot-readiness-hardening`.

The [audit/specification](phase7-pilot-readiness-spec.md) is preserved byte-for-byte (SHA-256 `af55ba1c335764431cd09806c25c582f3e0b5e264fc4f30d2960480044ff6743`). Its historical audit-only execution wording remains historical. This record supersedes execution status only; financial/business policy, original audit findings and evidence requirements remain unchanged.

## Approved decisions

| Decision | Approval | Authoritative execution profile |
| --- | --- | --- |
| D7-01 | APPROVED Option A | Managed PostgreSQL 17 with real commit provenance, private S3-compatible originals, Linux runtime, European-region target. Provider-neutral contracts; final paid provider/account/subprocessor/credentials/exact region are separate procurement/deployment decisions. |
| D7-02 | APPROVED Option A | Application logout, documented IdP SSO behavior, current local membership revocation and explicit offboarding. Logout does not claim to revoke offline-valid JWTs; no global logout expansion without real-provider need. |
| D7-03 | APPROVED Option A | Private exact-byte scan/quarantine before normal processing/download. Unknown/unavailable/suspicious/infected remain blocked; clean controlled release is tenant-isolated, auditable and retry-safe. No public scanner or third-party malware SaaS. Scanner classification is operational, never financial authority. |
| D7-04 | APPROVED Option A | Purpose-limited preservation, controlled revocation/offboarding and explicit reviewed retention/deletion. Preserve referenced immutable history; no universal retention period, silent destruction or legal/compliance claim. |
| D7-05 | APPROVED Option A | Internal RPO ≤1 hour and RTO ≤8 staffed hours, not SLA/guarantee. Actual backup/restore and original/history reconciliation are required before GO. Preserve real Phase 6 commit provenance; never fabricate K or substitute created_at. |
| D7-06 | APPROVED Option A | One explicitly enrolled company, controlled manual qualified intake, named owner/admin/analyst/viewer, supported deterministic layouts, explicit unsupported workflow and measured desktop workload. Chromium is the engineering baseline. No broad signup, many-company expansion, OCR, integrations or queue. |

## Approval separation

Specification and these six decisions are approved. Phase 7 implementation is authorized. Merge, production deployment, real customer pilot/data intake, purchases/infrastructure provisioning and repository administration changes are **not authorized** by this task. The implementation may become ready for review while pilot status remains NO-GO. Phase 8 and deferred product capabilities remain unimplemented.

Each blocking P0 gate receives exactly one evidence status: PASS; IMPLEMENTED / EXTERNAL EVIDENCE PENDING; or NOT IMPLEMENTED / BLOCKED. CI fixtures never substitute for real-provider, managed storage, deployed network, alert delivery or production-like restore evidence.

## Repository protection observation

On 4 October 2026 the GitHub connector returned HTTP 403 for main protection and ruleset reads. This does not establish whether protections exist. Status: **EXTERNAL / REPOSITORY-ADMIN EVIDENCE PENDING**. Recommended main protection: PR-based changes, no routine direct pushes, complete required checks and review before merge where supported, and no automatic Phase 7 merge. An administrator must provide evidence; settings changes require separate authorization. No paid plan upgrade or protection change was made.
