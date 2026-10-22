# FINLEAK Product V1.9 — Interactive criteria removal

Decision: **PASS DEVELOPMENT**, within the development evidence described below.
Date: 2026-10-19 UTC. Base commit: `0382c253d584aebed4a68f456fa116591404e91b`.
Branch: `dev/product-v19-interactive-criteria-20261019`.

## Delivered behavior

The existing Applied criteria panel has compact, individually named removal controls.
A click edits the existing queue filters, clears its cursor/history and starts the
same bounded server read used by form changes. The previous applied snapshot and URL
remain until that read succeeds. The summary and URL then describe the acknowledged
criteria. No financial decision or association mutation occurs.

The organization, order and page size remain non-removable information. An implicit
route default has no removal button. On review, explicit `needs_review=false` offers
**Restore default needs review filter**; it restores true rather than silently
broadening the default queue. Native buttons have specific accessible names and
keyboard activation. Accepted actions focus the persistent Applied criteria heading;
pending, success and failure are announced in a live status/error message. Controls
wrap with the existing definition list. No source UUID becomes a document name.

No second filter store, financial query engine or URL format was introduced. The
existing queue state remains the requested state, `AppliedCriteria` remains the
last successful snapshot, and V1.7 still validates and serializes the shared URL.
The new transition notice contains an action label/status and a request binding;
it is not another set of financial criteria or results.

## Removal contract

| Criterion                   | Action                                          | Other criteria retained                                                 |
| --------------------------- | ----------------------------------------------- | ----------------------------------------------------------------------- |
| Search text                 | Clear `q`                                       | Supplier, sources, currency, dates and presentation                     |
| Supplier                    | Clear `supplier`                                | Existing selected approved-association contract filter remains          |
| Contract                    | Clear `contract_source_id`                      | Supplier remains; no missing-contract filter or replacement is invented |
| Invoice source              | Clear `invoice_source_id`                       | Independent invoice document constraint remains                         |
| Invoice document            | Clear `invoice_document_id`                     | Independent invoice source constraint remains                           |
| Currency                    | Clear `currency`                                | Other filters remain; server currency separation remains                |
| Outcome                     | Clear `outcome`                                 | No outcome is recalculated or certified                                 |
| Decision status             | Clear `decision_status`                         | No recorded individual decision changes                                 |
| Created from                | Clear inclusive lower bound                     | Exclusive upper bound remains                                           |
| Created before              | Clear exclusive upper bound                     | Inclusive lower bound remains                                           |
| Current only                | Remove explicit current restriction             | Existing default is not restricted                                      |
| Needs review, anomalies     | Remove explicit true restriction                | Existing default is false / not restricted                              |
| Needs review, review        | Restore explicit false override to true         | Existing default restriction is retained                                |
| Missing contract            | Remove explicit missing-association restriction | No source is selected or approved                                       |
| Organization / order / size | No removal action                               | Existing organization selector and presentation controls remain         |

Supplier and contract are independent backend query constraints. Removing a supplier
restriction leaves a contract criterion valid and is therefore a single-field edit.
The existing supplier **form selector** still clears the contract when selecting or
clearing a supplier, preserving its historical behavior. This narrower summary
operation deliberately retains an already-selected contract; it creates no approval.
Invoice source and document are independently supported constraints and are also
removed separately. Contract+missing-contract is an invalid starting snapshot, so
it is rejected rather than repaired by inventing an association. Removing one date
bound leaves a valid one-sided period. UTC and Decimal semantics are unchanged.

A pure whitelist accepts only these 13 criterion keys. Organization, pagination,
sort, arbitrary keys and prototype names are rejected at runtime. It reuses V1.7
validation/defaults to check the snapshot and the next state. Summary lines carry an
optional criterion key; the clipboard formatter still uses only name/value, so the
V1.8 copy format remains unchanged.

## Controlled transition and error handling

1. Require an acknowledged current queue page and a same-organization applied snapshot.
2. Require the current membership-derived `criteriaAuthorized` gate from ProductConsole.
   The existing authenticated route guard and tenant-scoped API remain authoritative;
   this boolean is a UI capability gate, not an authentication substitute.
3. Verify that the selected criterion is explicitly removable under route defaults.
4. Construct a valid single-field patch and use existing `change(patch)`.
5. Update the corresponding form field, invalidate cursor/history, mark an edit pending.
6. A synchronous edit lock rejects a second rapid removal before React rerenders.
7. Existing effect cleanup aborts obsolete reads; aborted responses cannot publish
   a page, snapshot, URL or success notice.
8. Issue the usual bounded read (current page size, null continuation).
9. On success, record the snapshot, publish the existing validated URL and announce
   the completed action. The removal button disappears only after acknowledgment.
10. On failure, keep the last successful snapshot and URL, identify the requested
    action as unconfirmed/failed, and disable incoherent copy/removal actions.

A manual form edit supersedes a pending removal notice and uses the same existing
query path. Both Copy view link and Copy summary & link stay disabled while the
current page is unacknowledged. No stale cursor is used after changing criteria.
Organization changes remount the scoped queue and cancel its requests. Unknown or
inaccessible URL organizations are still blocked before financial reads.

After failure, existing **Retry this page** explicitly retries the requested read.
**Restore last applied criteria** instead replaces the draft with the existing
successful snapshot, resets pagination and requests a fresh read. It does not claim
restoration succeeded from cached results. There is no automatic retry of a failed
removal, no indefinite retry loop and no automatic financial decision replay.

Existing typed cursor recovery is unchanged and bounded to an active continuation.
A later pagination error does **not** relabel an already acknowledged removal as
failed. This case was found during implementation and has its own regression test.
Back/Forward and copied URLs restore criteria at the first page; local investigation
and Back preserve the current position, including after removal.

## Financial and privacy invariants

Backend code, money rules, role policies, source approvals, models, migrations,
decisions, mandatory reasons, double-submission protection, audit, evidence and
citations are byte-identical to V1.8. Signed server cursors, 100-candidate dynamic
limits and within-currency Decimal order are unchanged. No Recovery Ledger work.
The contract label cache now explicitly checks organization in the same way as the
existing invoice label cache; labels remain ephemeral and identifier-matched.

The summary still accepts criteria only. No amount, count, aggregate, quotation,
individual decision, review reason, token, cookie, server cursor or secret is added
to its text. Removing a criterion removes its line/URL parameter; unrelated labels
and search text are retained and can naturally contain the same words. It is not
string redaction or a DLP feature. Sharing copies plaintext criteria to the clipboard
and existing versioned URL; these can be sensitive in history/messages/logs. Existing
privacy warnings, no-access-grant caveat and length/Unicode guards remain intact.

No summaries are persisted, no sharing ACL/public link is created, no database schema
changes, no new dependency or endpoint. Removal starts reads only. Any compatible
member role can refine an authorized search; financial decisions retain the existing
separate role checks and authoritative endpoints.

## Actual verification

| Check                                       | Result                        | Scope                                                                                                     |
| ------------------------------------------- | ----------------------------- | --------------------------------------------------------------------------------------------------------- |
| Frontend Vitest                             | **371 PASS, 32 files**        | 324 unchanged historical tests + 47 new tests, explicit mocks/fixtures, separate Cloud scheduling profile |
| Backend targeted pytest                     | **294 PASS**                  | Existing pure financial/proof/transport/development tests; no native DB                                   |
| TypeScript / routes                         | PASS                          | Existing typecheck                                                                                        |
| ESLint                                      | PASS, zero warnings           | Existing strict lint                                                                                      |
| Prettier                                    | PASS                          | Frontend check; report formatted separately                                                               |
| Next.js build                               | PASS                          | Actual optimized 16.3.8 webpack build                                                                     |
| Ruff / Python format                        | PASS                          | Existing backend checks, 176 files formatted                                                              |
| Browser                                     | Actual compiled synthetic app | Keyboard removal, criteria preservation, clipboard, restoration, screenshots                              |
| Authenticated OIDC/PostgreSQL E2E           | BLOCKED                       | Not reinvestigated, not simulated as a native PASS                                                        |
| Native PostgreSQL, concurrency, performance | NOT VERIFIED                  | No native SQL, locks, query plans or benchmark                                                            |

New tests cover each optional field, independent contract/document/date constraints,
review defaults, invalid/prototype keys, preservation, cursor reset, bounded reads,
acknowledged snapshot/URL, failure and explicit restore/retry, rapid actions, canceled
late responses, authorization withdrawal, organization switch during a pending
removal, clipboard coherence and exclusions, actual heading focus/live announcements,
Back/Forward contract, investigation/back after removal, typed expired cursor recovery,
unavailable/ambiguous synthetic source and later-page error after a confirmed action.
No historical test was changed.

The first full run contained Cloud scheduling timeouts under default worker fanout,
and a new test's spy recursively referenced itself. The fixture was corrected and
a 369-test intermediate suite passed with **maxWorkers=2**. Subsequent standard-profile runs encountered scheduling timeouts even with one worker. The separate `vitest.product-v19-cloud.config.ts` profile uses one worker, 5-second asynchronous UI expectations and a 15-second per-test budget. Historical test files, assertions and the base config remain byte-identical; only the optional Cloud runner wait budgets change. A new test also allows three seconds for initial client mount/debounce. These results establish functional development behavior under those budgets, not compliance with a one-second latency cutoff or performance qualification.
Initial outputs, including the unhandled fixture error, are preserved separately
from final passing logs. A prior development venv was absent; ordinary locked
Python dependencies were recreated in the V1.9 helper directory without privileged
setup. This is not a runtime qualification or PostgreSQL investigation.

Reproduction from the existing frontend directory:

```text
./node_modules/.bin/vitest run --config vitest.product-v19-cloud.config.ts --reporter=default --reporter=json
npm run typecheck
npm run lint
npm run format:check
NEXT_TELEMETRY_DISABLED=1 ./node_modules/.bin/next build --webpack
```

Backend uses an isolated development environment created with existing `uv.lock`
and `uv sync --locked`, then:

```text
<venv>/bin/python -m pytest -q tests/test_money.py tests/test_financial_engine.py tests/test_proof_canonical.py tests/test_proof_assembly.py tests/test_oidc_transport.py tests/test_product_v11_development.py tests/test_product_v13_context.py tests/test_product_v14_query.py tests/test_product_v15_facets.py tests/test_product_v16_invoice_facets.py
<venv>/bin/ruff check .
<venv>/bin/ruff format --check .
```

No real OIDC session, user identity, financial transaction or database persistence is
claimed by these tests. Browser evidence is exclusively synthetic. The supervised
preview is internal QA and is stopped after capture; no user-facing hosted deployment.

## Limits and restoration

The UI authorization gate depends on the current session organization context; the
backend still checks every request. No native authorization or race qualification
is established. Current document labels can change between reads and remain labels,
not certified references or financial results. Clipboard refusals and server failures
are exercised by explicit component mocks; captured UI states are described according
to what was actually observed. Native buttons/focus/status are tested, but exhaustive
screen-reader and mobile viewport certification is not claimed. Concurrent removals
are serialized until a read finishes rather than combined in an implicit batch.

A page can reload to the last acknowledged URL while a draft removal is pending;
this is intentional. Errors do not silently widen that URL or provide an unconfirmed
share link. Existing login behavior still requires reopening the original link after
sign-in when needed. No new OIDC behavior or infrastructure was introduced.

The checkpoint contains complete source, exact V1.8 patch, changed file hashes,
this contract, final/raw logs, authentic captures, a guarantee/risk matrix and SHA-256
manifest. The patch is applied to the exact V1.8 source archive and compared byte for
byte with the complete delivered tree. The final ZIP is restored into a fresh directory
and all manifest entries rehashed. Main, historical commits, checkpoints and baseline
tests are preserved.

OIDC/PostgreSQL E2E stays **BLOCKED**. Native PostgreSQL, concurrency and performances
**NOT VERIFIED**. Phase 7, PostgreSQL/PITR and ClamAV/WSL **NOT QUALIFIED**. Scanner
**BLOCKED**, pilot **NO-GO**, PC and production **NOT AUTHORIZED**. No GitHub Actions,
paid service, public/prod deployment, real scanner or host execution occurred.

One concrete recommendation for V2.0: add personal named search views, isolated per
organization and containing only acknowledged criteria, without saved financial results.
