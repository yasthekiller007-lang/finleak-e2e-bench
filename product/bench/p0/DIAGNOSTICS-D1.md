# P0-D1 — scoped fixture diagnostics

This is a diagnostic change on `fix/p0-fixture-diagnostics`, based on the exact
first-run commit `e77169a19859716fb9c93d087d258f746dd1f726`. It authorizes no job.
No fixture precondition, financial rule, SQL constraint, permission, migration,
issuer validation, runner size or billing condition is relaxed.

## Confirmed masking mechanism

The first run `39851915526` reported fixture exit 2. `runtime.run()` captured its
stdout/stderr, recorded the return code, and raised a generic `RuntimeError`
before the caller's `json.loads()` could read the structured fixture result.
The outer handler exported only the exception class. Independently, the fixture's
preflight and CLI catch-all handlers collapsed multiple internal errors into
`database_or_test_issuer_preflight` / `fixture_or_witness_verification_failed`.
The emitter could only publish that already incomplete receipt. It was not the
point where the structured child reason was originally lost.

The original stdout/stderr were not exported. Their contents cannot be recovered
from the existing receipt. The exact cause of the first fixture block is still
**unknown**. Exit 2 alone does not establish a SQL, business or OIDC exception.
No reconstruction of a historical reason and no new service execution is used.

## Closed protocol

Only the known `acceptance.product_v11 seed` stage receives the new interpretation.
Other subprocesses retain their original nonzero/timeout handling. Child stdout
is parsed in memory, bounded to 16 KiB, never printed or persisted as a diagnostic.
Duplicate JSON keys, unknown fields, malformed or missing JSON, unexpected exit
codes, and contradictions stop execution. The bound limits accepted parsing; it
does not turn `subprocess.run(capture_output=True)` into a streaming memory cap.

| Child observation | Wrapper result | Public reason |
| --- | --- | --- |
| 0 + valid source-only `FIXTURE_ONLY`, zero financial records | Continue, never E2E PASS on this basis | `FIXTURE_PREPARED` |
| 2 + coherent `BLOCKED` | BLOCKED | Verified fixed precondition/internal code |
| 1 + coherent `FAIL` assertion result | FAIL | `FIXTURE_INVARIANT_FAILED` |
| Exit/status disagreement or unknown exit | FAIL | `FIXTURE_PROTOCOL_MISMATCH` |
| Absent/malformed/unverifiable JSON | FAIL | `DIAGNOSTIC_UNAVAILABLE` |
| Timeout before completion | BLOCKED | `FIXTURE_PROCESS_TIMEOUT`, exit code null |
| Process cannot be started | BLOCKED | `FIXTURE_PROCESS_UNAVAILABLE`, exit code null |
| Negative signal return code | BLOCKED | `FIXTURE_PROCESS_INTERRUPTED`, real negative code |

The new public `fixture_diagnostic` object has **exactly** these fields:

```json
{
  "schema_version": 1,
  "stage": "synthetic_document_identity_fixture",
  "exit_code": 2,
  "fixture_status": "BLOCKED",
  "reason_code": "POSTGRES_ROLE_REJECTED",
  "phase": "postgres_preflight",
  "category": "precondition",
  "e2e_executed": false
}
```

This example is synthetic, not a reconstruction of the first run.
`acceptance/p0_diagnostics.py` owns the finite code/phase/category combinations and
validates their types, ranges and consistency. Existing known `missing` constants
are mapped without exporting their values. A diagnostic supplied by the child
cannot invent a process timeout or override a contradictory missing-condition list.
Legacy generic database/OIDC preflight output remains `DIAGNOSTIC_UNAVAILABLE`:
the new parent deliberately does not infer which dependency failed.

Published precondition codes are `MISSING_TEST_PRECONDITION`,
`INVALID_LOOPBACK_CONFIGURATION`, `POSTGRES_VERSION_MISMATCH`,
`POSTGRES_ROLE_REJECTED`, `ALEMBIC_HEAD_MISMATCH`, `OIDC_DISCOVERY_REJECTED`,
`FIXTURE_DIRECTORY_NOT_FRESH`, `TEST_DATABASE_NOT_EMPTY`.
Exception codes are `DATABASE_PREFLIGHT_ERROR`, `ALEMBIC_PREFLIGHT_ERROR`,
`OIDC_DISCOVERY_ERROR`, `FIXTURE_PERSISTENCE_ERROR`,
`UNEXPECTED_INTERNAL_EXCEPTION`, `FIXTURE_INVARIANT_FAILED`.
The remaining codes are the parent process/protocol outcomes in the table.

Producer phases identify parameters, PostgreSQL preflight, Alembic, discovery,
fixture directory, storage initialization, database freshness, synthetic identities,
synthetic documents, transaction exit, or roster write. They identify the operation
in progress, not a speculative root cause. Catch-all CLI errors outside these
scopes retain `fixture_or_witness`; no exception message or traceback is exported.

## Security invariants and source lock

The original `v23-source.sha256` and its 425 entries stay byte-for-byte intact.
Only `backend/acceptance/product_v11.py` needs a diagnostic-only change in that
locked set. `gate.DIAGNOSTIC_SOURCE_OVERLAY` therefore pins **both** its historical
manifest digest and its exact replacement digest. All other 424 source files use
their original digests. A changed baseline entry, changed replacement, or symlink
still blocks. There is no wildcard exclusion, environment override or disabled
verification. The new diagnostic module and bench changes are additionally bound
by the separately reviewed full Git commit, as all bench code was before D1.
The historical test name referring to 425 original files remains unchanged; D1
explicitly documents the single pinned diagnostic overlay rather than claiming
that the actual fixture bytes are still identical.

The new diagnostic contains no raw exception, stdout/stderr, environment value,
HTTP response, SQL parameter, credential, path, customer data or financial record.
Its schema is checked before runtime receipt publication and again by the emitter.
The historical forbidden-word check remains additional defense; it is **not** an
absence-of-secrets proof or a schema for every legacy receipt field. This change
does not claim to qualify all historical evidence formats or arbitrary subprocesses.
No DEBUG mode, upload-artifact, cache, external export or dependency is added.

Fixture assertions remain FAIL, preconditions remain BLOCKED, cleanup failures
still force FAIL, partial migration/stage results are kept. All existing loopback,
synthetic-mode, role, empty-database, migration, PKCE/RS256 and storage checks remain.
The source fixture still inserts no evaluation, decision, financial revision or
proof package. The witness and financial computation logic are unchanged.

## Reproduce development validation — authorized Cloud workspace only

With the existing backend development dependencies installed, from the private
bench checkout root:

```bash
PYTHONPATH=product/backend:product/bench/p0 FLA_ENVIRONMENT=test python -m pytest product/bench/p0/tests product/backend/tests/test_product_v11_development.py -q
```

These are unit, contract and synthetic provider-protocol tests, not native
PostgreSQL or authenticated browser E2E evidence. New orchestration tests replace
the external processes explicitly, exercise the real wrapper branches, and check
partial receipts, cleanup success/failure and decoded base64 for canary disclosure.
They do not grant runtime execution or disable guards in delivered production code.

## Integrating a future candidate — no dispatch authorized by D1

Review this branch's one commit and its exact diff. The necessary executable
changes are the fixture and new diagnostic module, `runtime.py`, `emit_evidence.py`,
and the source-lock overlay in `gate.py`; include their tests and documentation.
The active workflow and its product template are deliberately unchanged.
Do not merge into the bench default branch without separate authorization.

Any new GitHub commit changes the immutable payload reference to approve. Before
a second run, review the final candidate SHA, its sole manual workflow, standard
`ubuntu-24.04` runner, single job, ten-minute limit, zero retries/artifact uploads,
and fresh authenticated owner billing evidence. The previous post-run observation
was **995 included minutes remaining, $0 displayed, $0 blocking budget**; it is a
historical snapshot, not a fresh gate approval. Retained root billing files are
historical and must not be treated as current authorization. Do not modify budgets
or spending protections and do not work around an actual GitHub refusal.

A second execution requires **new explicit authorization**. DIAGNOSTIC READY is
not E2E PASS. Phase 7/PITR/ClamAV remain NOT QUALIFIED, scanner BLOCKED, pilot
NO-GO, PC/production NOT AUTHORIZED.
