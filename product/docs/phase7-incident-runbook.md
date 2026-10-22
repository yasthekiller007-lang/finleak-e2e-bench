# Phase 7 incident and monitoring runbook

No deployed monitoring, alert recipient or staffed coverage is claimed. Name a primary and deputy, protected destinations, staffed hours and escalation/acknowledgment targets before pilot GO. No staff identities or SLA are invented. Test actual alert delivery in staging and record release/config/profiles/date/operator and both acknowledgments. Logs are operational diagnostics, never FinancialAudit or financial authority.

## Safe signals and routing

`pilot-logs/1` permits finite event names, server route templates, enumerated component/reason codes, UUID identities and bounded resource/status integers. Unknown messages/format arguments/provider exceptions, arbitrary extra values and traceback text are omitted. Production Uvicorn/provider handlers share this formatter so a reraised exception cannot bypass the sanitized API error handler. Root/provider unknown errors remain visible as `unclassified_event` and require controlled diagnosis; never enable raw DEBUG logging to obtain customer content.

Proxy and API errors use safe UUID correlation. Proxies copy only UUID X-Request-ID and bounded retry seconds; credentials/cookies are never forwarded in responses. Collect request ID, exact release/schema/profile and safe reason only. Restrict log access by operator role/tenant responsibility, encrypt transport/storage and qualify provider access/error-tracker scrubbing before intake. Infrastructure access logs must not record cookies, Authorization, source names/content, request/response bodies, bank data, amounts or complete query URLs. No telemetry SaaS receives originals or financial evidence under this task.

| Signal | Severity / response | Evidence required before pilot |
| --- | --- | --- |
| `readiness_failed`, DB 5xx / unsafe schema/guards/commit tracking | Critical if integrity/provenance is affected; suspend authority, verify independent liveness | Actual staging DB outage, migration/guard fault and restoration alert |
| `identity_unavailable` / repeated `identity_rejected` | High availability/security triage; preserve local fresh-role fencing; no auth fallback | Real-provider outage/rotation/invalid-token alerts and primary/deputy delivery |
| `source_store_failure`, source integrity or source gate failure | Critical for mismatch, high for outage; stop processing/download/recognition | Actual object-store outage/tamper alert with no source content |
| parser failure / needs_ocr / quarantined source | Operational warning or high recurring containment/scanner outage; leave unavailable | Unsupported-format, kernel protection and scanner-down alert |
| `proof_operation_failed` integrity reason | Critical; preserve immutable canonical/disclosure/history | Explicit integrity fault, safe code and correlation |
| recovery failure / `recovery_provenance_unresolved` | Critical for provenance/integrity; financial commit may already exist, inspect before retry | Captured/uncaptured boundary and safe alert without recreating money |
| repeated intake/proof/recovery rate or work limits | Warning; bounded error remains explicit, no hidden partial total | Shared-worker load and capacity evidence |

## Incident procedure

1. Record a protected incident identity, time, severity, exact release and safe request IDs; contact the named primary/deputy. Keep evidence outside public issues/chat/logs. Do not copy secrets or originals into diagnostic systems.
2. Contain through ingress suspension and explicit fenced user/tenant offboarding where appropriate. Keep liveness and operator access separate. Do not delete sources/history, disable guards, grant broad roles or use a test identity bypass.
3. For tenant/security exposure, preserve operational and FinancialAudit records, restrict access and follow separately approved legal/customer notification policy. This runbook does not authorize vendor communication or invent notification deadlines.
4. For object/scanner/parser outage, leave sources quarantined/unavailable. Reverify actual original bytes and explicit current clean scan/release after recovery. Never mark a file clean manually or transform its historical original.
5. For financial/proof/recovery integrity, freeze new positive authority. Compare immutable inputs/output/fingerprint/decisions/audits/provenance; do not edit money or repair/succeed a proof automatically. Use existing explicitly authorized correction/re-evaluation/reversal workflows separately.
6. For DB/restore faults, follow the backup/restore qualification. Never substitute created_at for original known-at or let a logical restore's new xmin certify old recovery history. No financial recalculation belongs in an operational restore.
7. Reopen only after guard, role, source, scanner, provenance and regression checks for the exact release, with attributed operator approval and separate deployment authority. Record remaining blockers, timeline and post-incident prevention.

## Specific outage handling

Database: fail closed, avoid repeated pool amplification, preserve committed versus uncertain outcomes and explicit idempotency keys. Storage: use protected inventory, inspect exact version/bytes, preserve uncertain orphan compensation. OIDC: no local bypass, document app logout versus provider SSO and already-issued token behavior. Scanner: engine/down/timeout/infected/suspicious stays closed; qualify private socket, engine/advisories and signatures/updater separately. Extraction: unsupported layout needs manual qualified review/re-export or rejection; no OCR or broadened automatic extraction. Proof: annotations/disclosure cannot edit canonical inputs; source availability is an overlay. Recovery: claims, issued credits, net/costs, reversals and historical receipts remain separate; recovery exceptions never silently rewrite finding truth.
