# FINLEAK Product V2.2 — saved view lost-response reconciliation

**PASS DEVELOPMENT**, for the implemented V2.2 behavior and applicable development
checks. This does **not** mean the complete frontend suite passes: its actual
result is **552 PASS / 1 FAIL / 553 total**, with no skipped tests. The frozen
V2.0 assertion remains incompatible with approved V2.1 behavior. It is unchanged,
its failure is retained, and a minimal proposed migration is isolated and not
applied. OIDC/PostgreSQL E2E remains separately BLOCKED.

## Continuity and scope

Continued exactly from V2.1 commit `ef0bc17acc32a0bf4a367bb89af991702a45849c`,
branch `dev/product-v22-lost-response-reconciliation-20261019`. The reference ZIP
SHA-256 is `337446b8e001ef4121a639646eaf6fc58921ce9e3507a95770fb2c1591256389`.
Its CRC, all 460 manifest entries and complete source were checked. Main and all
prior local branch references are preserved. No backend, dependency, financial
rule, historical test, runner profile or migration was modified.

The increment reuses the existing saved-view gateway, authorized GET, strict
`parseSavedView`, `savedDefinition`, `compareSavedCriteria` and `definitionKey`.
It does not create another persistence service, financial model, API endpoint,
database table or migration. The proposed historical-test patch is documentation,
not an applied test change.

## Ephemeral attempt contract

Immediately before the explicitly confirmed criteria PATCH, `replacementAttempt`
validates and copies the authorized saved record and exact proposed definition.
The captured context contains the view ID, organization, owner, name, original
revision, criteria before replacement, canonical criteria actually sent, ordinary
view timestamps, a local UI reference and issue kind. It contains no financial
results, case counts, decisions, decision reasons, excerpts, citations, server
financial cursor, credentials or token. The copied definitions and criteria are
frozen. The local `local-N` reference is scoped to the component session and is
explicitly labelled as UI correlation, never a server transaction ID.

The proposal is the same immutable object passed to the existing gateway.
Subsequent applied filters cannot change what this attempt proposed. An identical
definition cannot create an attempt or PATCH. Issue kinds distinguish a pending
response, timeout, unverified/transport failure, HTTP error and explicit version
conflict. A generic thrown gateway error may not reveal whether the failure
occurred in transport or parsing; this uncertainty is retained, not converted to
a claim about commit/rollback.

The context is React memory only. It is cleared on acknowledged success, selection
replacement, scope remount, loss of access or unmount. It is not persisted to
PostgreSQL, browser storage, URLs or a log. The UI explicitly states that after a
page reload attribution of a previous operation is unavailable. No attempt is
reconstructed from a matching saved-view name or criteria.

## Reconciliation engine and four-state matrix

`reconcileSavedReplacement(before, proposed, observed, organization, owner, demo)`
is pure. It revalidates both snapshots and the observed record, including exact
view ID, owner, organization, view type, format and safe positive integer
revisions. Unsupported fields, malformed values and foreign records yield an
unavailable result without copying their unverified name or data into the output.
Different names never establish identity; identical names never merge records.

The result contains only `kind`, `observed_revision`, `proposed_matches`,
`previous_matches` and `reason`. The existing 15-property canonical equality and
route-specific defaults apply. Document identity remains structured; labels do
not determine equality. The state includes the revision, not only the criteria.

| State                                | Required observation                                                                                                               | Meaning and permitted next step                                                                                                                          |
| ------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| A — PROPOSED_CRITERIA_OBSERVED       | Proposal matches at original revision + 1                                                                                          | “Proposed criteria found in the saved view.” Current state observed, no transactional attribution. New review or another explicit read.                  |
| B — PREVIOUS_CRITERIA_STILL_OBSERVED | Previous criteria match at unchanged revision                                                                                      | “Previous criteria are still recorded as of the latest read.” No conclusion of definitive write failure. New review or explicit read.                    |
| C — DIFFERENT_SAVED_STATE_OBSERVED   | Other criteria, or a revision progression inconsistent with the expected single replacement                                        | “The saved view differs from both compared states.” Never overwrite it; fresh comparison and explicit confirmation required.                             |
| D — RECONCILIATION_UNAVAILABLE       | Read failed/cancelled/timed out, inaccessible/deleted record, malformed or foreign data, revision older than the starting snapshot | “Unable to determine the saved state.” The outcome remains unknown. Offer a new authorized read; review actions remain disabled until a verifiable read. |

A proposal at the same revision is C, not a success. Previous criteria after a
revision increment are C: a rename, later update or other change may have occurred.
Multiple increments are C even if the proposal now matches; the panel explicitly
states whether the criteria match and explains the unexpected version progression.
An older revision is D because its reliability as a current observation cannot be
established. There is no server receipt or transaction-attribution guarantee in
the existing API. Even A does not prove which actor or request caused the state.

## UI and request lifecycle

`Saved view reconciliation` shows the authorized view name, original and observed
revisions where available, observed comparison, certainty limits and next action.
The panel differentiates an unconfirmed write, a read in progress, an observed
state, an unavailable read and a requirement for fresh review. It never displays
“Successfully saved” based on reconciliation. It does not show criteria values,
raw UUIDs, financial results or protected document content.

`Check saved view state` sends exactly one authorized GET for the captured view.
It never invokes update/delete or a financial mutation. A synchronous guard
serializes rapid clicks. A separate abort controller and generation counter
reject obsolete replies after cancellation, timeout, another read, selection or
scope change, even when an explicit test double ignores its abort signal.
The read is capped at 30 seconds in the panel; the existing live gateway also
retains its unchanged transport deadline. Timeout abandons observation and allows
another manual read. It does not imply that an earlier write was rolled back.

The read does not depend on the financial form having an applied snapshot, so an
analyst can check an earlier attempt while changing filters. Reconciliation never
replaces those filters or re-applies financial results. A validated response may
refresh the selected saved record; the old replacement review stays invalid.

On 409, the explicit rejected request is identified as a conflict; the proposed
criteria and name draft are retained. A fresh GET and new comparison are required
before another write. On transport loss, HTTP error or mismatched response, the
write outcome is unconfirmed. No second PATCH is issued. A successful GET after
an uncertain write can lead to A, B or C; a failed GET leads to D, never to a
declaration that the write failed.

401/403 stops the reconciliation, cancels pending operations and clears private
saved-view state, names, drafts and attempt context. Further saved-view reads and
writes are disabled for that component instance until an authorized scope is
re-established. Membership remains authoritative on the backend. A 404 reveals
no foreign record and leaves the outcome unknown; a later authorized read can be
requested. Other read failures show a generic message without echoing untrusted
upstream details.

`Review changes again` uses the original V2.1 fresh-read/comparison/confirmation
path and current authoritative expected revision. It never replays the old PATCH.
After D, review actions in both the summary and old diff are disabled. A separately
successful ordinary reload also clears the former reconciliation observation;
it does not silently declare the old attempt successful.

`Close summary` cancels an active read, retains the in-memory uncertain attempt
for another explicit check and returns focus to `My saved views`. It performs no
mutation. Scope changes remount the panel and abort obsolete reads. The heading
receives focus when the summary opens. Status changes use a polite atomic live
region; controls are keyboard-operable and wrap on narrow screens. Native screen
reader and mobile-device qualification has not been performed.

## Actual verification

- **57 new V2.2 tests PASS**: 28 pure-state cases and 29 component/synthetic-gateway
  cases. Coverage includes all four states, revisions, homonyms, malformed/foreign
  responses, 401/403/404/409, timeout, repeated reads, out-of-order replies, scope
  loss, closing, no replay, no-op review and data minimization.
- The initial targeted run also executed all 59 V2.1 tests: **116/116 PASS**.
- Final complete frontend diagnostic: **552 PASS, 1 FAIL, 553 total, 0 skipped**.
  This includes the new tests and 495 passing pre-existing tests. It is not a
  complete-suite PASS. The unchanged optional V1.9 Cloud profile remains one
  worker, 5-second async assertion budget and 15-second test timeout. No assertion,
  historical file or scheduling profile was relaxed.
- Backend: **371 targeted development tests PASS**, using the existing locked
  development venv. Pure validation, API/session doubles and compiled SQL are not
  native OIDC/PostgreSQL evidence.
- TypeScript, zero-warning ESLint, Prettier, optimized Next.js webpack build,
  Ruff and Python formatting: **PASS**, with actual logs included.
- Browser: all four states exercised in the optimized application through the
  existing in-memory demo gateway, with explicit synthetic fault controls. The
  unavailable-read exercise recovered only after another manual read; A followed
  by fresh review showed `No changes to save`; keyboard closure returned focus to
  the persistent heading. Unmodified Cloud JPEG screenshots are included.

The browser faults are intentionally synthetic: recorded-in-memory, previous
criteria, a later divergent memory state and one failed read. The fault selector
never affects the authenticated gateway and never establishes native transport,
identity, PostgreSQL persistence or transaction concurrency. The internal preview
was stopped. No public deployment or hosted preview was created.

Initial logs are retained. ESLint initially found a missing callback dependency
and ref declarations used before effect analysis; callbacks were stabilized and
refs moved before their use, without disabling a lint rule. Browser review found
that D still offered the fresh-review action; it was disabled in both panels,
with new assertions, followed by targeted/full tests and rebuild. The earlier
full diagnostic and unavailable-state screenshot remain as initial observations.

## Historical incompatibility and unapplied proposal

The retained failing test is
`frontend/tests/product-v20-saved-workspace.test.tsx` /
`renames without replacing criteria and requires explicit update confirmation`.
It expects `Confirm update criteria` synchronously and a criteria PATCH after a
name-only rename with identical current criteria. Approved V2.1 instead requires
a fresh asynchronous GET, `Confirm replacement`, and no PATCH/revision increment
for no differences. The diagnostic fails at the former label; its following
no-op write expectation is also incompatible. No hidden alias, skip or useless
write was introduced to satisfy it.

`docs/proposals/product-v22-historical-test-migration.proposed.patch` changes only
that obsolete confirmation block to await `No changes to save`, check the disabled
new confirmation and retain one name-only PATCH at revision 2. `git apply --check`
passed against the untouched historical file. **The patch was not applied and the
modified test was not executed. Its adoption requires separate approval.** Existing
V2.1 tests cover name-only rename followed by a genuinely different replacement,
fresh re-read revision, no-op refusal and exact payload. V2.2 adds the explicit
reconciliation/no-replay/new-no-op-review cases. PASS DEVELOPMENT here describes
the applicable approved feature contract; the known red full-suite result remains
reported separately and the acceptance migration remains open.

## Delivery, reproduction and limits

The checkpoint includes complete tracked source, the exact V2.1-to-V2.2 patch,
changed-file hashes, this contract, the four-state matrix, full/targeted logs,
initial observations, simulated-race evidence, preservation checks and screenshots.
The exact patch and ZIP were restored into fresh isolated Cloud directories and
compared byte for byte, including every manifest entry. The manifest excludes
itself. No active `.env`, keys, credentials, dependencies, caches or `.git` are
packaged. Historical tests, backend and migrations are byte-identical to V2.1.

Use the existing lockfile/development environment. From `frontend/`, run the
existing Cloud-profile Vitest command, typecheck, lint, format check and build.
The two new `product-v22-reconciliation*` test files provide focused verification.
The complete diagnostic must retain its historical failure until separate
approval of the proposed migration. Reproduction commands and actual outcomes
are included; they grant no additional execution authorization.

Cancellation cannot roll back an already dispatched PATCH. A read is a snapshot
and may be followed by concurrent activity. Timestamp/criteria equality cannot
establish transaction identity; native commit, races, restart durability and
performance remain unverified. The app makes no recovered-money claim.

OIDC/PostgreSQL E2E: **BLOCKED**. Migration `0010`: **NOT APPLIED**. Native
PostgreSQL persistence/concurrency/performance: **NOT VERIFIED**.
Phase 7/PITR/ClamAV: **NOT QUALIFIED**. Scanner: **BLOCKED**. Pilot: **NO-GO**.
PC and production: **NOT AUTHORIZED**. No blocked infrastructure investigation
was repeated and no financial rule, decision or Recovery Ledger was changed.

Next product action for V2.3: add explicit lost-response reconciliation for
personal-view renames, with the same fresh-read and no-automatic-replay rules.
