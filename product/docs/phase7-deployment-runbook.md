# Phase 7 deployment and release contract

This is a future staging/pilot procedure, not evidence of deployment. [Execution decisions](phase7-implementation-decisions.md) authorize implementation only. No cloud vendor, account, exact region, subprocessor, credentials, paid resource or production tenant is selected. The target is European-region managed PostgreSQL 17, private S3-compatible originals and Linux.

## Isolation and identities

Use distinct synthetic staging and pilot databases, buckets/prefix policies, OIDC clients, secrets, networks and operator rosters. No customer data in CI/development/staging. Only the HTTPS frontend ingress is public. Backend, database, scanner and originals remain private; no direct backend host port or public object URL. The illustrative [staging compose contract](../deploy/phase7/compose.staging.yaml) creates no managed service. Its outbound network must be constrained by the separately reviewed hosting firewall. The health probe Host must be explicitly permitted by the final private-network profile.

Production secrets are delivered at runtime through approved protected secret injection. Never put them in images, build arguments, browser variables, command-line URLs, release reports or logs. Certificate/CA material is mounted read-only and verified, not disabled. DB requires `sslmode=verify-full`; object and OIDC endpoints require HTTPS. Scanner is a private trusted service, never a public malware service.

## Database roles

`python -m app.operations.roles bootstrap --apply` defines dedicated NOLOGIN `fla_migration`, `fla_app`, `fla_operator`, `fla_scanner` groups without passwords or tenant membership. Run only in an explicitly approved target with an authorized provisioning connection. The code refuses existing unsafe privileged groups and does not reassign ownership or downgrade credentials automatically. Configure separate protected login identities externally, with only the appropriate group; application must not inherit migration/operator/scanner authority.

Run migrations as the dedicated migration owner using `FLA_MIGRATION_ROLE=fla_migration` and a separate login that can assume it. Fresh objects must be owned by that role. For an existing database, owner reconciliation requires explicit review; no automatic ownership conversion is provided. App cannot own schema/tables, create database/schema objects, become privileged, disable triggers or set replication bypass. Re-run `grant-runtime --apply` after each migration under the reviewed owner/admin connection; verify the resulting allowlist before admission.

Current tenant and membership `FOR UPDATE` fencing requires UPDATE privilege on a column. Application is granted only `UPDATE(id)` on those two tables, never membership role/user/tenant writes or organization insertion. Migration 0007 guards stable IDs against mutation. The operator group manages roster/access availability and reads its journal, with no financial write grants. App cannot write availability or the operator journal. FinancialAudit remains trigger-origin; no blanket future table privilege is granted. Follow the [access runbook](phase7-access-runbook.md) for explicit enrollment, transfer/revocation and offboarding.

Budget total connections as replicas × workers × (pool size + overflow), plus dedicated scan/admission/operating connections and migration/admin allowance. Initial per-worker pool is 5 with zero overflow and five-second wait; this is a setting, not throughput evidence. Measure before enrollment. The runtime is one process per container with bounded worker subprocesses, not a queue.

## Source availability contract

Migration 0009 records immutable exact-byte scan history, controlled releases and pinned request aliases. There is no legacy auto-clean backfill. Unknown, unavailable, timed-out, infected, suspicious or mismatched originals remain privately retained and blocked. An explicit new scan is required after a failed verdict; an explicit owner/admin release of the current clean scan is required for normal content/process/proof/recovery byte reads. A new failed scan closes an older release without changing historical financial/proof/recovery snapshots. Source scanning/release never approves financial facts, evaluates, generates/repairs/reviews proofs or recognizes recovery. Analysts can request scans; viewers read status; owner/admin control release. Clean is an operational result, not a safety/legal/financial guarantee.

Production requires `FLA_SCANNER_SOCKET_PATH` for a protected absolute Unix socket, and a separate TLS-verified `FLA_SCANNER_DATABASE_URL` using only the scanner group. The scanner can append scan/request history and lock current tenant/source/membership rows via immutable id-column privileges; it cannot release sources, change roster or write financial/proof/recovery authority. The application cannot insert scan verdicts. Both role/readiness profiles and all seven new guards must pass. A literal loopback TCP adapter exists only for engineering protocol fixtures; production construction rejects it. No external scan service receives originals.

Provision the private local daemon/socket and its signature-update process only after separate deployment authorization. Protect the socket directory from untrusted mutation, restrict socket permissions to the required application/scanner identities, isolate scanner filesystem/network/resource scope and record qualified engine/signature versions. No such daemon deployment or real provider qualification is claimed. Real ClamAV integration, parser containment, deployed socket/role permissions and fresh signatures must be validated before GO; the transport fixture alone does not satisfy them. The compose contract's final socket mount/scanner image remains part of that qualification.

## Exact release

1. Require separate authorization before deploying staging or pilot. Verify approved roster, provider/data agreements and no customer intake before GO.
2. Pin the intended Git SHA, complete push/PR CI, schema head and operational profiles. Preserve checkpoint history. Do not merge automatically.
3. Build [backend image](../deploy/phase7/backend.Dockerfile) and [frontend image](../deploy/phase7/frontend.Dockerfile) with `RELEASE_SHA` equal to that exact commit. Versioned base-image defaults are engineering inputs, not a qualification claim: resolve/pin their digests and scan the resulting images before staging approval. No runtime test/identity harness or tests are copied into images.
4. Record image digests, base digests, lockfile hashes, migration revision, release SHA, build date/runner and vulnerability evidence in a protected release manifest without secrets. Use immutable image digests in deployment settings; never `latest` or floating application tags.
5. Capture a reconciled backup before migration; execute the migration job with its dedicated role. No startup auto-migration inside application traffic processes. Run schema drift and privilege/trigger checks.
6. Start private application, storage/scanner and frontend under their separate environment files. Production entrypoints reject test/development mode or missing release identity. Read-only filesystem, non-root identities, dropped capabilities, no-new-privileges and bounded tmpfs are the default contract.
7. Readiness must pass schema/PG/commit tracking/role/TLS/store/scanner checks. Liveness alone cannot admit traffic. Run all synthetic acceptance/fault tests and capture genuine provider evidence.
8. Verify HTTPS/ingress/host/proxy controls and source persistence across replacement; document monitored primary/deputy and alerts.
9. Drain ingress before replacement; SIGTERM allows up to 35 seconds for backend work and compose allows 40 seconds. Verify actual hosting drain behavior and interruption/retry semantics, not just settings.
10. Independent review of every P0/AC7 outcome and explicit customer/operator/pilot authorization precede any real intake. Missing blocking evidence means NO-GO.

## Rollback and protection

Application rollback must remain compatible with the applied schema and immutable historical rule/proof/recovery versions. Never downgrade populated financial/proof/recovery/operational history to make an old image start. Restore or forward repair is explicit and evidence-backed; no hidden financial recalculation. Repository-admin evidence for main protection remains pending after 403 connector reads. Require PR changes, successful complete CI and review where supported; no routine direct push and no automatic Phase 7 merge. No settings change is authorized here.
