# FINLEAK Product V1.8 — Applied criteria summary

Decision: **PASS DEVELOPMENT** (development scope only). Date: 2026-10-19 UTC.
Base: `e5b36a02c205217216bc980882eb08a9e56f4aaa`, Product V1.7.
Branch: `dev/product-v18-criteria-summary-20261019`.

## Implemented increment

The anomalies and human review queues now show an **Applied criteria** section with
**Copy summary & link**, while keeping **Copy view link** separately unchanged.
The reusable component receives a criteria snapshot only, never a financial result
page, count, assessment, decision, reason, citation or proof package. No new URL
format, endpoint, financial rule, permission, database model or dependency was added.

A successful, non-aborted queue read records the organization, filters and page size
used by that read. The summary represents that snapshot. Edited controls do not
replace it until their own query succeeds. During debounce, pagination, refresh,
network error or a pending replacement read, it explicitly identifies the last
successful criteria and disables copying. Before the first success, it shows a
waiting state; a first-read failure has a distinct message. A different organization
cannot display the preceding organization's snapshot. Existing URL guards still
block invalid scope before any financial component or search is mounted.

Copy is possible only when the current queue page is acknowledged and its criteria
are coherent. The text and link are produced together from the same validated
snapshot. Clipboard success is shown only after the awaited browser operation
resolves. Pending, refusal/unavailable clipboard and invalid/unrepresentable link
have distinct handling. Clipboard requests occur only on a user button action.
A label change cannot enable a second concurrent summary-copy request while one
is pending. An obsolete completion cannot show success for different criteria.

The new section uses neutral labels and a wrapping semantic definition list. It
has a named region, heading, native button, descriptive pending/error messages and
status announcement after success. Text wraps rather than hiding criteria by
ellipsis. No exhaustive mobile viewport or screen-reader certification is claimed.

## Summary and clipboard contract

`criteriaLines` reuses V1.7 `validatedCriteria` and `viewPath` validation. It is a
presentation adapter, not another financial query model. `summaryText` checks the
supplied URL using the existing parser and requires byte equality with the canonical
V1.7 URL for the exact organization, criteria, view mode and page size. A different
filter, organization, route, synthetic/live prefix, unknown field, secret parameter,
fragment, credentials or oversized URL is rejected. Backend cursors are never inputs.

| Display / copied line                | Semantics                                                                           |
| ------------------------------------ | ----------------------------------------------------------------------------------- |
| Organization                         | Name from the currently authorized organization context                             |
| Search text                          | Validated and trimmed recorded-value query; not a result or excerpt                 |
| Recorded supplier name               | Exact stored string; preserves case and spacing; no legal-entity consolidation      |
| Approved-association contract filter | Selected contract criterion, not an association approval                            |
| Invoice source document              | Authorized current document label, not a verified invoice number                    |
| Invoice document constraint          | Independent document criterion; a source label is reused only if document IDs match |
| Currency filter                      | Exact uppercase currency criterion; no cross-currency arithmetic                    |
| Outcome filter                       | Readable description of the existing outcome enum                                   |
| Recorded decision filter             | Existing historical-status criterion, never an individual decision                  |
| Created from / before                | Canonical UTC timestamps; inclusive lower and exclusive upper bound                 |
| Current assessments filter           | Current only / Not restricted; filtering is not a validity certification            |
| Needs human review filter            | Yes / Not restricted; review route defaults to Yes, anomalies to Not restricted     |
| Missing contract filter              | No unique association returned / Not restricted, preserving existing semantics      |
| Sort                                 | Existing order label; amount order remains within currency                          |
| Page size                            | Requested page size, not a result count or current page position                    |

Optional absent criteria are omitted. The three boolean filter meanings, order and
page size remain explicit. A default view shows **No optional filters selected**;
turning off the review route's default is treated as an explicit default deviation.
The link restores criteria, not the current cursor position or results.

The clipboard contains plain text: a FINLEAK heading (explicitly **Synthetic** in
demo mode), the whitelisted criterion lines, the existing versioned view link,
and short access/current-data/privacy caveats. The text never reads results to
construct itself. Counts, anomaly amounts, aggregation, scope explanations, quotes,
review reasons, individual decisions and arbitrary metadata fields are excluded.
A currency criterion and page-size setting are intentionally included, as requested.

The complete text is bounded to **12,000 UTF-16 code units**; the V1.7 complete URL
remains bounded to 4,096 characters. Values are never silently truncated. Invalid
criteria, an invalid/mismatching link, overlong output or ill-formed Unicode refuse
summary copying. Unicode line/directional control characters in criteria also refuse
structured sharing so they cannot forge extra lines or reorder meaning. This adds a
presentation-only restriction; it changes no backend filter policy or V1.7 URL format.

Names are displayed only as labels. Missing, UUID-like, control-containing or over-512
code-unit document/organization labels receive an explicit neutral unavailable label.
The criterion's identifier stays selected and remains internal to the existing link.
An unavailable label never causes a replacement source or association. Criteria text
itself is validated rather than silently shortened. Unicode and special characters
in ordinary names/searches are retained without Base64 or confidentiality claims.

## Authorized labels without redundant reads

The existing `SourceFacetSelect` now offers a narrow optional label notification.
It publishes only the selected source ID, current authorized label and document ID.
The summary consumes this existing selector resolution; it does not call the gateway
or fetch documents itself. Its addition causes **zero additional label requests**.
Invoice page labels retain their document ID so an independent matching document
criterion is correctly described. Descriptions, excerpts and monetary fields are
never propagated into summary labels. Labels are matched by organization, kind,
source ID and, where relevant, document ID. They are ephemeral React state only.

V1.7's existing resolution remains bounded: at most two existing scoped GETs per
selected source needing resolution (source detail, document detail), plus explicit
selector retries. Current page labels and explicit facet selections can already
supply a label without another read. Unavailable labels remain explicit; existing
selector retry controls remain available. A label can still be pending/unavailable
when criteria succeed; copying then uses the explicit neutral label, never an
invented name. A subsequently resolved label changes the summary's copy identity.

## Privacy and financial invariants

No summary is stored in a database, local storage, session storage or a results log.
No public-access grant, sharing ACL, public deployment, API mutation or automatic
clipboard operation was introduced. Copy, restoration and cursor recovery do not
submit financial decisions. Existing reason requirements, role checks, authoritative
responses, double-decision protections, 409 handling and audit remain untouched.
The backend, OIDC implementation, Decimal engine, approved associations, source
provenance, citations, signed cursors and 100-candidate dynamic-filter limit are
byte-identical to V1.7. Recovery Ledger implementation remains unauthorized.

Criteria and document labels themselves can be sensitive. The UI preserves V1.7's
history/sharing-log warning and the copied text warns about its audience. A clipboard
is ordinary plaintext; other clipboard consumers, histories, messages or logs can
retain it. Existing frontend `Referrer-Policy: no-referrer` is unchanged; deployment
behavior and retention are not qualified by this increment. A link grants no access
and does not freeze, certify or export a financial result. Search text can contain
user-supplied sensitive values; this feature is not a DLP system.

## Actual development verification

| Check                                         | Result                              | Practical scope                                                                                                                                  |
| --------------------------------------------- | ----------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| Frontend Vitest                               | **324 PASS, 30 files**              | 293 unchanged V1.7 tests + 31 new tests; explicit component/API mocks                                                                            |
| Backend targeted pytest                       | **294 PASS**                        | Existing pure financial/proof/transport and development-boundary tests; no native database                                                       |
| TypeScript / route types                      | PASS                                | Existing typecheck command                                                                                                                       |
| ESLint                                        | PASS, zero warnings                 | Existing strict lint command                                                                                                                     |
| Prettier                                      | PASS                                | Frontend check; this report formatted separately                                                                                                 |
| Next.js optimized build                       | PASS                                | Actual Next.js 16.3.8 webpack build                                                                                                              |
| Ruff / Python format                          | PASS                                | Unchanged backend, 176 files formatted                                                                                                           |
| Cloud browser                                 | Observed synthetic compiled product | Clipboard, applied criteria, existing link, restoration, pending-state observation and screenshots (network failures covered by component tests) |
| Authenticated OIDC/PostgreSQL E2E             | BLOCKED                             | Historical limitation, not reinvestigated                                                                                                        |
| Native PostgreSQL / concurrency / performance | NOT VERIFIED                        | No SQL execution, lock tests, query plans or benchmark                                                                                           |

Tests include defaults, review differences, supplier/contract/invoice combinations,
homonymous document names as distinct criteria, missing labels, UTC offsets, outcomes,
decision filters, sort/page size, pending drafts, failures/retry, obsolete response
suppression, organization isolation, URL restoration/history, clipboard pending/refusal,
invalid scope/link/length, secret/result/excerpt exclusion, V1.7 copy compatibility,
synthetic labeling, no decision mutation, exact text/link consistency and matching
independent invoice document labels. They do not demonstrate an OIDC session or a
PostgreSQL transaction. No historical test was edited to make V1.8 pass.

The previous development venv was no longer present. A new isolated dependency
environment was created under the V1.8 helper directory using existing `uv.lock`
with `uv sync --locked`, CPython 3.12.14 and no privileged setup. Dependency install
output is retained. Frontend dependencies, manifests and backend lockfile are unchanged.
Initial new-test loading timing, unsupported Testing Library `exact` role options,
and the Unicode presentation test were corrected; initial logs are retained
separately from final passing logs. An independent document label propagation case
was added and corrected by retaining the existing authorized row's document ID.

Reproduction commands, from the respective existing project directories:

```text
frontend: vitest run --reporter=default --reporter=json
frontend: npm run typecheck
frontend: npm run lint
frontend: npm run format:check
frontend: NEXT_TELEMETRY_DISABLED=1 ./node_modules/.bin/next build --webpack
backend: <isolated-venv>/bin/python -m pytest -q tests/test_money.py tests/test_financial_engine.py tests/test_proof_canonical.py tests/test_proof_assembly.py tests/test_oidc_transport.py tests/test_product_v11_development.py tests/test_product_v13_context.py tests/test_product_v14_query.py tests/test_product_v15_facets.py tests/test_product_v16_invoice_facets.py
backend: <isolated-venv>/bin/ruff check .
backend: <isolated-venv>/bin/ruff format --check .
```

## Limits and next increment

Names may change between authorized reads and remain document labels, not frozen
financial facts. Same-name documents are not merged; the existing source identifiers
in the view link retain the actual criterion. A pending query's draft is not shareable;
refresh restores the last acknowledged V1.7 URL. Back/Forward starts fresh pagination;
local investigation/back retains its existing position. The existing unauthenticated
login behavior still requires reopening the original link after sign-in when needed.
No OIDC shortcut, native SQL substitute or new infrastructure investigation was used.

Phase 7, PostgreSQL/PITR and ClamAV/WSL remain **NOT QUALIFIED**. Scanner **BLOCKED**;
pilot **NO-GO**; PC and production **NOT AUTHORIZED**. No GitHub Actions, paid Cloud
resource, public deployment or real scanner was used. A dependency installation in
this isolated development workspace is not a runtime qualification.

The checkpoint includes complete source, exact V1.7 patch, changed-file hashes,
summary contract, raw/final logs, authentic synthetic screenshots, risk matrix,
manifest and restoration evidence. The supplied patch is applied to the exact
V1.7 git archive and compared with every delivered source byte. The final ZIP is
extracted into a fresh directory and every manifest entry is rehashed. Historical
archives, branch heads, main and baseline tests are preserved.

One concrete V1.9 recommendation: add per-criterion removal controls to the applied
summary, reusing the existing server query and acknowledged-state safeguards.
