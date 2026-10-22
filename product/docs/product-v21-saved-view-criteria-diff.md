# FINLEAK Product V2.1 — saved view criteria diff

Decision: **PARTIAL DEVELOPMENT**. The criteria comparison and safe replacement
are implemented and the 59 new development tests pass. The complete unchanged
historical suite has one incompatible V2.0 assertion: it expects the former
confirmation label and a replacement for identical criteria. V2.1 deliberately
requires an asynchronous authorized re-read, `Confirm replacement`, and no PATCH
for identical criteria. That historical test is retained and its failure is
reported; the complete frontend suite is not presented as passing. Native
OIDC/PostgreSQL validation remains separately BLOCKED.

## Checkpoint and implementation

Continued from V2.0 commit `0ee728a33c730d24aad054bc1ae217d0eea2dcd0` on isolated
branch `dev/product-v21-saved-view-diff-20261019`. The V2.0 ZIP SHA-256 is
`d5c2b240f2b2fcc13a62dec9328391ebc872051c08b617f311355f8b64df7056`.
All 462 manifest entries and 411 source files were independently compared.
No previous checkpoint, historical test, runner profile, backend endpoint,
financial rule, authorization policy, dependency or migration was changed.
The existing gateway and optimistic revision protocol remain authoritative.

The delivered increment adds a pure criteria comparison, a compact accessible
before/after panel and a confirmation bound to the reviewed criteria and
re-read saved revision. It extends the existing `getCurrent`, `canSave` and
`confirm === "update"` mechanisms. There is no second saved-view service and no
financial-result comparison, storage or decision mutation.

## Comparison contract

`compareSavedCriteria(before, after, demo = false)` accepts only definitions
accepted by the unchanged V2.0 `savedDefinition` and V1.7 criteria validator.
It rejects unsupported format versions, different view types, unknown keys,
cursor fields, malformed dates/UUIDs and invalid page sizes. Demo page size 2 is
accepted only when explicitly requested with `demo: true`. Production page sizes
remain 20/50/100. No validator was relaxed.

The result contains `saved`, `current`, `rows`, `counts` and `hasChanges`.
`saved` and `current` are copied canonical definitions with frozen criteria.
Rows are ordered by the following 15 properties, not by labels or source order:

| Property            | Meaning                                                 |
| ------------------- | ------------------------------------------------------- |
| q                   | Search text                                             |
| supplier            | Recorded supplier name, not consolidated legal identity |
| contract_source_id  | Approved-association contract filter                    |
| invoice_source_id   | Invoice source document                                 |
| invoice_document_id | Invoice document constraint                             |
| currency            | Currency filter                                         |
| outcome             | Recorded assessment outcome filter                      |
| decision_status     | Recorded decision filter, not an individual decision    |
| created_from        | Inclusive UTC start                                     |
| created_to          | Exclusive UTC end                                       |
| current             | Current-assessment restriction                          |
| needs_review        | Needs-human-review restriction                          |
| missing_contract    | No unique approved association restriction              |
| sort                | Existing server sort                                    |
| page_size           | Existing bounded page size                              |

Each row contains the normalized structured `before`/`after` values and one of
ADDED, REMOVED, CHANGED or UNCHANGED. An absent optional value is `null`; adding or
removing it is distinguished from changing one defined value to another.
Approved normalization trims search text, normalizes UUID case and UTC dates,
and retains supplier string case/spacing equality. Absent `current` and
`missing_contract` mean unrestricted, like explicit false. `needs_review`
retains route semantics: absence on `/review` defaults to true; explicit false
is different; absence on `/anomalies` defaults to false. Sort defaults to newest.
These defaults come from existing validators and query contracts.

`definitionKey` is an ordered JSON tuple of type, format and normalized values.
It is an in-memory equality marker, not a cryptographic proof, permission check,
database version or additional saved state. Criteria-edit version metadata is
an event counter tied to the existing successful applied snapshot. It detects
even edits that return to the original value before a render. It is never sent
to the backend or persisted.

Document UUIDs remain internal equality values. Distinct IDs always change the
row even if names are identical. Display labels are optional copies of labels
already available in the authorized applied snapshot, keyed by field and ID,
and scoped to organization and user. No extra label API was invented. Missing
labels explicitly say unavailable; an identical filename never proves identical
document identity. Older saved labels that are unavailable are not guessed.

Only criterion counts are shown. No anomaly amount, case count, decision reason,
citation, invoice excerpt, financial cursor, cookie, token or secret is included
in the structured comparison. A user-entered search string or supplier name may
itself be sensitive; it retains the existing authorized visibility and is not
logged by this feature or included in a new persistence layer.

## Safe replacement protocol

1. `Update saved criteria` requires the authorized owner/organization, selected
   view and an applied snapshot from a successful active financial read.
   Existing URL coherence and synchronous pending-edit guards are retained.
2. Capture the proposed validated criteria and criteria-edit version, then GET
   the selected view through the existing authorized gateway. Opening performs
   no write. Validate returned owner, organization, view type and ID.
3. Build the comparison from the fresh saved definition and captured proposal.
   If the saved revision changed, show the newly read revision and the change
   notice. Re-check criteria and edit version after the read. A late read cannot
   make an obsolete comparison confirmable.
4. Focus `Review saved view changes`. Show saved name, re-read revision,
   changed rows, counts and native keyboard-accessible unchanged disclosure.
   The table scrolls horizontally on narrow screens. Manual mobile device or
   assistive-technology qualification has not been performed.
5. Enable `Confirm replacement` only for actual differences, unchanged context,
   known matching selected revision and an uninvalidated review. On click,
   re-check `getCurrent()`, edit version and structured definition equality.
   A change followed by restoration of the former filter still requires review.
6. Send exactly the displayed canonical proposal and `expected_revision` through
   the existing PATCH. A synchronous in-flight guard prevents rapid duplicates.
   No financial decision, result or name draft is attached to this operation.
7. Accept success only after an authorized parsed response returns the same ID,
   owner, organization, expected revision + 1 and the displayed criteria.
   Otherwise the outcome is unconfirmed. No optimistic success is displayed.
8. A 409 retains the current filters, comparison and name draft, blocks writes
   and requires an explicit fresh read/comparison. No write is replayed.
   A lost response may have committed; explicit reload reconciles the record,
   invalidates the former review and allows a new comparison. If the proposal
   is already saved, it becomes `No changes to save` with no additional PATCH.
9. `Cancel` never mutates. Focus returns to the update trigger, or the persistent
   saved-views heading if a pending financial read disabled that trigger.
   Owner/organization/type/membership changes remount the scoped panel, abort
   obsolete requests and clear private saved state. Aborting a dispatched write
   is not a server rollback; later reconciliation remains necessary.

Criteria changed after a PATCH was already dispatched cannot revoke that request.
The request still contains the exact earlier reviewed snapshot, and normal
backend membership/owner/revision checks remain authoritative. Native database
race behavior has not been validated in this environment.

## Other V2.0 operations

Create, search, bounded saved-view pagination, open, name-only rename and separate
confirmed deletion remain on the original gateway. Opening still requests a
fresh first-page financial read, not stored results. No automatic approval or
Recovery Ledger was introduced. A new V2.1 regression test verifies name-only
rename followed by a separately reviewed replacement with the fresh revision.
Existing no-op tests verify no PATCH and no artificial revision increment.

## Actual development verification

- New V2.1 tests: **59 PASS** (pure comparisons and components using explicit
  synthetic gateways/transport doubles).
- Complete frontend release diagnostic: **495 PASS, 1 FAIL, 496 total**, with no
  skipped tests. The one historical failure is detailed below. This count is
  not a declaration that all frontend tests pass.
- Backend targeted development suite: **371 PASS**. Existing locked V1.9 venv;
  pure validation, API/session doubles and compiled SQL, not native PostgreSQL.
- TypeScript, ESLint with zero warnings, Prettier, optimized Next.js build,
  Ruff and Python formatting: **PASS**, according to included final logs.
- Same unchanged V1.9 optional Cloud frontend profile: one worker, 5-second
  async assertion budget and 15-second per-test timeout. These are scheduling
  budgets, not application performance evidence. No test assertion or historical
  configuration was changed, skipped or replaced to hide a failure.

The unchanged historical test is
`product-v20-saved-workspace.test.tsx` /
`renames without replacing criteria and requires explicit update confirmation`.
It synchronously looks for `Confirm update criteria`, then expects PATCH after
renaming without changing the criteria. V2.1 requires a fresh asynchronous GET,
the new `Confirm replacement` action, and no write for an unchanged definition.
The diagnostic fails at the former label lookup; its later no-op PATCH
expectation is also incompatible with the explicit new requirements. No hidden
alias, fallback action, test skip or no-op mutation was added to satisfy it.
The remaining 436 historical frontend tests pass. The replacement path is
covered by new tests, but changing the frozen acceptance assertion requires a
separate decision, hence the conservative PARTIAL DEVELOPMENT verdict.

Initial verification observations are retained: TypeScript found three optional
label dereferences, corrected with optional chaining; the first complete suite
reported 493/494 with the same historical incompatibility. Browser QA found
focus loss when cancelling while the trigger was disabled; a fallback to the
persistent heading and a targeted regression test corrected that real defect.
Final tests include two additional cases for that fallback and rename separation.

The browser exercised the actual optimized bundle only in isolated synthetic
mode: a saved version 1 compared with applied EUR/oldest/page 20 showed one
removal and three changes; keyboard confirmation received a synthetic memory
acknowledgment and version 2; the next review showed all 15 unchanged and a
disabled confirmation. Editing a filter invalidated the open review. Screenshots
are unmodified remote Cloud browser JPEGs. No live API, OIDC session or database
operation is established by those captures. The supervised internal preview was
stopped; no public deployment or hosted preview was created.

## Reproduction and residual limits

Restore `checkpoint/` into a new isolated Cloud working directory. Use the
existing frontend lockfile/development dependencies and the unchanged commands
recorded in evidence. Run the full test diagnostic without suppressing its
documented historical failure. For focused feature verification run both
`product-v21-criteria-diff.test.ts` and `product-v21-replacement.test.tsx` with
`vitest.product-v19-cloud.config.ts`. Typecheck, lint, format and build use the
existing package scripts. The package contains the exact V2.0 patch, complete
source and preservation evidence. Patch and ZIP restoration were compared byte
for byte. SHA-256 manifests exclude their own file by definition.

There is no new migration or backend change. Candidate migration `0010` remains
**NOT APPLIED**. Native OIDC/PostgreSQL E2E remains **BLOCKED**; native saved-view
persistence, concurrent writes, grants, restarts and performance remain
**NOT VERIFIED**. No UID, PostgreSQL, Docker, OIDC or R1 investigation was repeated.
Phase 7/PITR/ClamAV: **NOT QUALIFIED**. Scanner: **BLOCKED**. Pilot: **NO-GO**.
PC and production: **NOT AUTHORIZED**. Development results lift no restriction.

Next product action for V2.2: add an explicit reconciliation summary showing
whether the proposed saved criteria were found after an uncertain replacement,
using fresh authorized reads and without replaying the write.
