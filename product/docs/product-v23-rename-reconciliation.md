# FINLEAK Product V2.3 — rename lost-response reconciliation

Decision: **PASS DEVELOPMENT** for the implemented feature and applicable
development checks. The full frontend diagnostic remains **611 PASS / 1 FAIL /
612 total**, with no skipped tests. Its unchanged V2.0 assertion is incompatible
with approved V2.1 behavior. The proposed test migration remains **NOT APPLIED**.
This is not a declaration that the full suite passes, nor native E2E validation.

## Original checkpoint recovery

The original V2.2 ZIP was recovered from the retained files and independently
verified against SHA-256
`dcb3deca4931c1e3f519f390e3e690e0e05d3617f3ee55c18ace154f6352fa7d`.
All 471 manifest entries and ZIP CRC passed. The transient checkout available at
the start had reverted to V1.9; no missing product code was reconstructed from
reports or memory. Original V2.0/V2.1 archives were also retrieved and verified.
Their archived patches restored their exact source trees. Git commit objects were
accepted only after their complete bytes reproduced the original IDs exactly:
`0ee728a`, `ef0bc17`, `5069934`. Existing refs and working files were untouched.
The restored V2.2 tree contains 422 source files and is the sole code baseline.

Development uses a separate worktree/branch,
`dev/product-v23-rename-reconciliation-20261019`, descending from
`50699347835a96210c62d5d78642a2165300c683`. Restoration evidence is included.
Main, prior checkpoints, historical tests and the V2.2 test-migration proposal are
preserved. Existing locked Cloud development dependencies are reused; no package
was added, no GitHub Actions job was run, and no infrastructure investigation was
repeated.

## Attempt and comparison contracts

The existing reconciliation module gains a discriminated `RenameAttempt`; the
V2.2 `ReplacementAttempt` structure remains unchanged. Both use the same in-memory
attempt slot, local UI sequence, authorized gateway, abort controller, 30-second
read deadline, request generation counter and access-loss cleanup. This is not
another persistence service or API.

`renameAttempt(before, proposedName, org, owner, localId, demo)` strictly parses
the existing saved record. It captures the exact view ID, authorized owner and
organization, old display name, validated proposed name, original revision,
previous criteria definition, ordinary view timestamps, local UI reference and
issue kind. Names use the unchanged `savedName`: NFKC, trimmed/collapsed whitespace,
1–80 code points, no forbidden control/format/surrogate characters. Effective
equality uses the normalized display name; a case-only display change remains a
change. Existing backend uniqueness rules remain authoritative and unchanged.
The frontend does not invent a new case-folding or collision policy.

The old record and criteria are copied/frozen before dispatch. The PATCH is
exactly `{name, expected_revision}` through the existing gateway; it contains no
criteria replacement. A normalized unchanged name produces `No name changes to
save`, no PATCH and no artificial revision increment. The local `local-N` reference
is explicitly UI correlation, not a server transaction identifier.

No financial results, amounts, case counts, decisions, reasons, citations, document
excerpts, credentials or financial cursor are captured. No attempt is stored in
PostgreSQL, browser storage, a URL or a new log. Names themselves can be sensitive
and remain subject to the existing owner/organization visibility. Page reload or
context loss discards attribution context, as explicitly stated in the UI.

`reconcileSavedRename(before, proposedName, observed, org, owner, demo)` is pure.
It validates both records and exact ID/owner/org/type/format, normalized names,
safe positive revisions and the structured criteria definition. It reuses
`definitionKey` and existing validators rather than labels or JSON display text.
The result adds optional `criteria_unchanged` for rename observations while
preserving the V2.2 replacement result contract. Raw records or foreign names are
not copied into unavailable results.

## Four-state matrix

| State                              | Conditions after authorized GET                                                                         | Interpretation and next action                                                                                                                                            |
| ---------------------------------- | ------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| A — PROPOSED_NAME_OBSERVED         | Proposed normalized name, original revision + 1, all criteria unchanged                                 | “Proposed name found in the saved view.” Current state observed; no proof this precise attempt performed it. Read again or review a new rename.                           |
| B — PREVIOUS_NAME_STILL_OBSERVED   | Previous name, original revision, all criteria unchanged                                                | “Previous name is still recorded as of the latest read.” Not definitive write failure. Read again or start a fresh rename review.                                         |
| C — DIFFERENT_SAVED_STATE_OBSERVED | Other name, changed criteria, or incompatible revision progression                                      | Never overwrite. A matching proposed name alone is insufficient. Fresh authorized read, review and explicit confirmation required.                                        |
| D — RECONCILIATION_UNAVAILABLE     | Read error, cancellation/timeout, missing/inaccessible record, malformed/foreign data or older revision | Outcome unknown. Another explicit bounded read is available; new-review actions remain disabled until a verifiable read. 401/403 clears private context and stops access. |

Multiple increments are C even if the proposed name matches. The original name
after an increment is C. The proposed name without an increment is C. A matching
name with changed currency, source identity, route semantics or page size is C.
An older revision is D because it cannot reliably establish the latest state.
Neither a name match nor an expected revision is transaction attribution.

## Product workflow and concurrency

The ordinary initial `Rename view` action remains a name-only explicit write.
Before its PATCH, the parsed record and proposal are captured. Acknowledgment is
accepted only if the authorized response has the exact ID/type/scope, proposed
name, expected revision + 1 and identical structured criteria. Otherwise the
outcome stays unconfirmed. A synthetic memory acknowledgment is explicitly labelled
as synthetic; an observed GET result never shows `Rename successful`.

After timeout, transport loss, error or unverified response, the existing summary
now displays `Operation: Rename saved view`, both names, initial/observed revisions,
observed state, certainty and permitted next action. `Check rename state` performs
one GET for the exact captured view. It does not update, delete, choose a homonymous
record or mutate a financial decision. Rapid clicks are serialized. Cancellation,
timeout, selection and scope changes invalidate obsolete responses even if an
explicit test double ignores AbortSignal. A cancelled GET is not a server rollback.

`Review rename again` reads the current record afresh and opens a separate
`Review saved view rename` panel. It shows current/proposed name and re-read
revision. The old draft is retained. It does not depend on financial-query
readiness: renaming saved metadata does not save applied search criteria.
No write occurs until `Confirm rename`. Editing the name invalidates the review,
even if the draft is restored. Cancellation performs no mutation and returns
focus to the persistent saved-views heading. If the proposed name is already
recorded, the panel disables confirmation and sends no second PATCH.

The existing `Reload personal views` action still makes the rename action
available after a valid manual read. If an uncertain rename context remains,
clicking `Rename view` then opens a fresh rename review instead of sending a PATCH.
This preserves the historical recovery affordance and requires explicit new
confirmation; it does not replay the uncertain request.

Confirmation checks the selected ID/revision, reviewed name and structured
criteria snapshot. The new request is name-only with the freshly read revision.
A concurrent criterion/name edit after review yields backend HTTP 409. No
authorization or uniqueness check is bypassed. Concurrent criteria from the new
read are preserved, not replaced by the original attempt’s criteria.

401/403 clears protected names, drafts, review and attempt state, aborts pending
operations and disables further saved-view access in that scoped instance. 404
retains uncertainty without revealing a foreign record. 409 preserves the draft
and requires fresh review; it is not retried. Other read errors permit another
explicit bounded read and do not prove write failure. `Close summary` cancels its
GET and returns keyboard focus while retaining the uncertain in-memory context.

The summary uses the existing semantic section, focus heading, polite atomic live
region and responsive styling. The fresh-review heading receives focus after its
request finishes, so it is not focused inside a disabled loading fieldset.
Native screen-reader and mobile-device audits have not been performed.

## Actual development checks

- New V2.3 tests: **59 PASS** — 30 pure-state and 29 component/transport-double
  cases. They cover loss, A/B/C/D, Unicode/no-op/collision, changed criteria,
  unexpected revision, foreign/homonymous records, authorization/context loss,
  late replies, cancellation, timeout, double click, no replay, explicit fresh
  confirmation and authoritative response validation.
- Final full frontend: **611 PASS, 1 FAIL, 612 total, 0 skipped**. All 552
  applicable pre-existing tests and 59 new tests pass. The known historical
  failure is retained, not hidden or reclassified as full-suite success.
- Backend targeted: **371 PASS** in the existing locked Cloud venv. Validation,
  API/session doubles and compiled SQL are not native PostgreSQL/OIDC proof.
- TypeScript, zero-warning ESLint, Prettier, optimized Next.js webpack build,
  Ruff and Python formatting: **PASS** according to actual final logs.
- Existing optional V1.9 Cloud test profile is byte-identical: one worker,
  async assertion budget 5 seconds and per-test timeout 15 seconds. No historical
  assertion, file or timeout was relaxed.

Initial failures are retained. The first targeted run had 114/116 PASS, including
57 V2.2 tests and two failing new V2.3 cases. The review heading was focused before
the loading fieldset became enabled; focus is now deferred until the request ends.
The deferred double-click fixture tried to release its Promise before the resolver
was installed; it now waits for that explicit readiness. ESLint required the new
setter in the memoized access-cleanup dependency list. TypeScript rejected browser-
API-style `exact` options in the new Testing Library tests and a duplicate object
property in one new fixture; those typing defects were corrected. No lint rule or
historical test was suppressed. Initial and final logs are included.

The first complete run collected 603 tests (601 PASS, 2 FAIL) and three additional
Node test files failed at import, leaving nine cases uncollected. That run overlapped
the dependency symlink-to-copy correction needed by the isolated preview. After
the dependency copy was stable, the nine cases collected and passed without any
test/config change. The other applicable assertion failure exposed the disabled
rename action after manual reload; its recovery affordance was restored as
described above. The focused compatibility run then had 59 PASS and only the
known historical FAIL. All initial diagnostics are retained; the final complete
run is reported separately above.

Browser QA exercises the optimized app only in clearly marked synthetic mode,
using four new fault options in the existing in-memory saved-view fixture. These
simulate a committed rename with lost response, unchanged name, a matching new
name followed by a criterion change, and an unavailable first read. The normal
authenticated gateway is unaffected. Captures are unmodified Cloud JPEG bytes,
not mockup images. The supervised internal preview was stopped; no public hosting
or production deployment was created.

## Preserved historical failure and limits

The unchanged V2.0 test
`renames without replacing criteria and requires explicit update confirmation`
in `product-v20-saved-workspace.test.tsx` expects the former criteria-confirmation
label synchronously and then a criteria PATCH with no difference. V2.1 requires a
fresh GET, `Confirm replacement`, and no no-op write. The full diagnostic therefore
still fails at the old label. No hidden alias, skip or unnecessary PATCH was added.
The V2.2 proposal at
`docs/proposals/product-v22-historical-test-migration.proposed.patch` is preserved
byte for byte and remains unapproved/unapplied. New rename tests do not replace it.

The checkpoint contains the full source, exact V2.2 patch, changed-file hashes,
this contract, four-state/security matrices, real logs, simulated concurrency
results, original-baseline restoration proof and authentic synthetic screenshots.
The exact patch and ZIP were restored into fresh Cloud directories and all source
bytes/manifest entries verified. The manifest excludes itself. No `.git`, active
`.env`, credentials, dependencies, caches or upload receipts are packaged.

The GET is an observation, not a transaction receipt, and can be followed by later
changes. No native persistence/restart/race/performance conclusion follows from
memory fixtures or mocked failures. A dispatched PATCH cannot be rolled back by
cancelling its browser response. All backend code, financial calculations,
currency handling, permissions, audit, proofs and migration files are unchanged.

E2E OIDC/PostgreSQL: **BLOCKED**. Migration `0010`: **NOT APPLIED**. Native
PostgreSQL persistence/concurrency/performance: **NOT VERIFIED**.
Phase 7/PITR/ClamAV: **NOT QUALIFIED**. Scanner: **BLOCKED**. Pilot: **NO-GO**.
PC and production: **NOT AUTHORIZED**. No new execution is authorized by this report.

Next product action for V2.4: add an explicit state check after an uncertain
personal-view deletion, without automatic DELETE replay or financial mutation.
