# FINLEAK Product V1.7 — Shareable exception views

Decision: **PASS DEVELOPMENT**. Date: 2026-10-19 UTC.

V1.7 adds usable criteria-only links to the existing server exceptions queue and
human review queue. It continues V1.6 commit
`b4403ae4a9b835a452aea7a316443066c35f225e` on
`dev/product-v17-shareable-views-20261019`. No backend financial rule, model,
migration, authorization policy or historical test was modified. No new dependency.

## Implemented behavior

- Copy view link uses the browser clipboard and confirms only its resolved success.
  It is disabled until the current server query succeeds, and during a pending copy.
  Refusal/unavailable clipboard and an unrepresentable link have explicit recoverable
  messages. The control is a native keyboard-accessible button.
- The anomalies and review routes validate raw browser parameters and organization
  membership before mounting any financial workspace. Malformed, unknown, duplicate,
  unsupported or unauthorized parameters produce a generic blocking error. A separate
  explicit button opens the first authorized organization's default view. An invalid
  organization is never silently substituted.
- Reopening/restoring a link starts fresh bounded queries at the first page. Invoice
  and contract IDs remain selected even when their source becomes unavailable. The
  current label is resolved by at most two existing authorized BFF GETs per source:
  financial source detail, then document detail. Source ID/kind and document
  ID/organization must match. A missing label is explicitly unavailable with retry;
  no replacement option or association is invented. Returned document names are
  current labels, not certified contractual references. No full facet scan is used.
- Successful acknowledged criteria update browser history; drafts and failed queries
  do not overwrite the last valid link. Back/Forward remounts the financial context
  and queue with fresh pagination. Own criteria writes do not remount it on each page.
  Investigation and local Back retain the current queue position. Organization
  switching aborts old reads, clears the old criteria/pagination and starts defaults
  for an authorized organization. Late aborted responses cannot replace active data.
- Existing native login redirect, tenant-scoped BFF, financial decisions, evidence,
  audit, dynamic 100-candidate limit, Decimal order and currency separation remain.
  Copy, restore and pagination recovery perform reads only; they never replay a decision.
- Demo links stay under `/demo/`; live links stay under `/anomalies` or `/review`.
  Demo data/decisions are in-memory synthetic examples, prominently labeled.

## Versioned URL contract

Canonical paths: `/anomalies?ev=1&org=<uuid>&...` or `/review?...`.
Synthetic equivalents add the `/demo` prefix. Output order follows the table below;
`ev=1` and `org` precede criteria, and `ev_limit` follows them. URLSearchParams
encodes UTF-8 and special characters; this is public text encoding, not encryption.
The entire absolute URL is limited to **4096 characters**, checked on restoration,
copy and history writes. Unknown filter object fields are never serialized.

| Parameter                                              | Validation / meaning                                                                                                         |
| ------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------- |
| `ev`                                                   | Exactly `1`; required for all `ev_` parameters                                                                               |
| `org`                                                  | UUID, canonical lowercase; mandatory for versioned links; session membership required                                        |
| `ev_q`                                                 | Up to 160 JavaScript UTF-16 code units, trimmed as existing query semantics                                                  |
| `ev_supplier`                                          | Exact snapshot string, 1–120 code units; case/spacing preserved; not a legal identity                                        |
| `ev_invoice_source_id`                                 | UUID; reviewed invoice source constraint                                                                                     |
| `ev_invoice_document_id`                               | UUID; independent invoice document constraint, visibly retained and clearable                                                |
| `ev_contract_source_id`                                | UUID; existing approved-association filter, never approval itself                                                            |
| `ev_currency`                                          | Three uppercase ASCII letters; no cross-currency addition                                                                    |
| `ev_outcome`                                           | POTENTIAL_LEAKAGE, NEEDS_REVIEW, NO_OVERCHARGE or UNDERCHARGE                                                                |
| `ev_decision_status`                                   | confirmed, false_positive, needs_review or unrecorded                                                                        |
| `ev_created_from`, `ev_created_to`                     | Explicit timezone ISO date-time; millisecond precision at most; UTC canonicalized; from strictly before to when both present |
| `ev_current`, `ev_needs_review`, `ev_missing_contract` | Exact lowercase true/false                                                                                                   |
| `ev_sort`                                              | newest, oldest, amount_high, amount_low or outcome                                                                           |
| `ev_limit`                                             | Live: 20/50/100; synthetic: 2/20/50/100                                                                                      |

Dates must be real calendar days, have valid times and a timezone. Control characters,
malformed percent/UTF-8 encoding, ill-formed Unicode, empty explicit criteria,
repeated decoded keys, unknown keys, trailing separators and invalid IDs are rejected.
Missing-contract and an explicit contract cannot coexist. Defaults are newest, no
optional constraints, needs_review=false for anomalies / true for review, page size
20 live / 2 demo. Default-valued fields are omitted; explicit review false is retained.
False current/missing_contract have the same backend meaning as absence.

Legacy `org`, `invoice` and `assessment` links remain accepted (UUIDs validated).
An absent organization on a valid legacy/unfiltered link uses the first authorized
organization, matching the existing initial-entry convention. Legacy invoice becomes
an invoice-source criterion. Assessment opens the existing investigation; copied links
exclude it. Versioned links cannot include legacy invoice (ambiguous double meaning).
Assessment is allowed on input for legacy investigation compatibility but is never
serialized into a shared view. Duplicate searchParams are preserved for rejection.

No OIDC token, cookie, secret, cursor key, backend continuation, quotation, financial
result or decision reason is read into the serializer. Any such named URL parameter
is rejected. URLs restore criteria against current accessible data; amounts and counts
can change, and a shared link certifies neither a result nor a source's currentness.

**Privacy:** supplier/search/IDs/dates themselves can be sensitive. They are visible
in browser history, address bars, request/access logs, copied messages and potentially
referrer handling by the existing deployment. Do not put secrets in search values or
send links outside the intended authorized audience. V1.7 adds no grant, public link,
shortener, saved-view backend or logging-redaction guarantee. The interface warns
before sharing. Existing deployment retention/referrer policy remains a separate issue.

## Cursor recovery contract

| Scope                                                      | Expected response on an active continuation             | Action                                                                                       |
| ---------------------------------------------------------- | ------------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| Exception queue                                            | 409 EXCEPTIONS_CHANGED or 422 INVALID_EXCEPTIONS_CURSOR | Discard only queue navigation; same criteria/size; one fresh first-page read; visible notice |
| Open facet choices                                         | 409 FACETS_CHANGED or 422 INVALID_FACET_CURSOR          | Discard only facet navigation; same facet/search/context; one first-page read; notice        |
| Facet's underlying exception filter                        | 422 INVALID_EXCEPTIONS_CURSOR                           | Same bounded facet restart                                                                   |
| First-page error, network error, unrelated 409, auth error | No automatic recovery                                   | Show existing error/retry controls                                                           |

The error's status and machine code must both match; a message alone is insufficient.
A restart is possible only when an active continuation exists. Its replacement query
has no continuation, so another failure cannot produce an automatic loop. Manual retry
is explicit. Signed server cursors remain ephemeral and internal React state; no new
backend signing or pagination behavior was introduced. Synthetic fixture cursors do
not prove signature enforcement; unchanged backend unit tests cover that contract.

## Tests and observations

Newly executed in this isolated Work Cloud:

| Check                            | Actual result            | Scope                                                                                                                                                                             |
| -------------------------------- | ------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Frontend Vitest                  | **293 passed, 28 files** | 225 unchanged historical tests + 68 new tests; explicit component/API mocks and synthetic fixtures                                                                                |
| Backend targeted pytest          | **294 passed**           | Existing financial/Decimal/proof/OIDC transport and V1.1/V1.3–V1.6 development tests; no DB execution                                                                            |
| TypeScript / Next route types    | PASS                     | `npm run typecheck`                                                                                                                                                               |
| ESLint                           | PASS, zero warnings      | `npm run lint`                                                                                                                                                                    |
| Production compilation           | PASS                     | Next.js 16.3.8, webpack, actual optimized build                                                                                                                                   |
| Prettier                         | PASS                     | Frontend format check; final report also formatted                                                                                                                                |
| Ruff / Python formatting         | PASS                     | Existing 176 backend files formatted; no backend code changed                                                                                                                     |
| Cloud browser                    | Observed working         | Compiled synthetic app, actual clipboard via Enter, copied link in new tab, reload, Back/Forward, empty result, investigation/back, page 2 retained, invalid organization refusal |
| Real OIDC/PostgreSQL integration | BLOCKED                  | Historical limitation, not reinvestigated or simulated as success                                                                                                                 |

Commands and complete raw output are in evidence/. Frontend new tests cover malformed
URLs/Unicode, version/defaults/legacy compatibility, IDs/size bounds, secret/cursor
exclusion, invalid organization before reads, current criteria history, organization
abort, stale response suppression, unavailable source labels and retry, read-only label
resolution, clipboard pending/refusal, typed cursor recovery, first-page retry bounds,
and unchanged unauthenticated redirect. No real login is claimed by route mocks.

Backend command (existing development venv, no privileged setup):

```text
.venv/bin/python -m pytest -q tests/test_money.py tests/test_financial_engine.py tests/test_proof_canonical.py tests/test_proof_assembly.py tests/test_oidc_transport.py tests/test_product_v11_development.py tests/test_product_v13_context.py tests/test_product_v14_query.py tests/test_product_v15_facets.py tests/test_product_v16_invoice_facets.py
```

Frontend: `vitest run --reporter=default --reporter=json`, `npm run typecheck`,
`npm run lint`, `npm run format:check`, and
`NEXT_TELEMETRY_DISABLED=1 ./node_modules/.bin/next build --webpack`.
The managed preview was internal only and stopped after QA. No public deployment.
Browser diagnostics included extension metadata errors from the browser environment;
these are not financial application results or evidence of an authenticated session.

Initial new-test failures (wrong fixture count/button names and a resolver used after
its variable had been replaced), an initial lint dependency warning, and a wrong
Python invocation without the existing venv were corrected. Raw initial logs are
retained separately from final passing results. A defensive label-ID check was added.
Historical tests were never edited to make V1.7 pass.

## Guarantees, limits and remaining risks

| Item                                           | Status                             | Evidence / limit                                                                    |
| ---------------------------------------------- | ---------------------------------- | ----------------------------------------------------------------------------------- |
| Versioned sharing/restoration                  | PASS DEVELOPMENT                   | Implemented in actual routes and compiled app; mocks are explicit                   |
| Invalid scope before financial requests        | PASS development contract          | Guard precedes financial component mount; invalid-link gateway spies see zero reads |
| Read-only copy/restore/recovery                | PASS development contract          | New code has no decision writes; mutation spies and byte-identical backend          |
| Historical preservation                        | PASS after checkpoint verification | Exact V1.6 source/manifest, all baseline tests and branch heads checked by packager |
| Native PostgreSQL, concurrency and performance | NOT VERIFIED                       | No native DB execution, locks, plans or benchmarks                                  |
| Authenticated OIDC/PostgreSQL E2E              | BLOCKED                            | No actual login or persisted transaction demonstrated                               |
| Phase 7, PostgreSQL/PITR, ClamAV/WSL           | NOT QUALIFIED                      | No qualification attempted                                                          |
| Scanner                                        | BLOCKED                            | Not executed                                                                        |
| Pilot                                          | NO-GO                              | Unchanged                                                                           |
| PC and production                              | NOT AUTHORIZED                     | Neither accessed                                                                    |

No saved views or permissions are created. No backend schema/route/index change.
Existing financial API parameters and responses are unchanged. Source metadata is
resolved at most once per selection/mount plus explicit retries; authorized labels
may change between reads and are not snapshots of an old result. Network failures
preserve the selected ID. Keyboard operation uses native controls and existing facet
navigation; no exhaustive screen-reader/mobile audit was performed.

The existing login route does not preserve a return URL across an unauthenticated
login. Users follow the existing sign-in behavior and can reopen their original link
after signing in. No OIDC shortcut or test JWT injection was added. Browser history
updates only acknowledged filter changes (250 ms query debounce); a pending draft
can be lost on refresh, deliberately leaving the last valid URL. Back/Forward restores
criteria at page one; only local investigation/back retains ephemeral cursor position.
Other page-navigation links keep their existing default-view behavior.

## Checkpoint and restoration

The delivery includes the full tracked source, exact V1.6-to-V1.7 binary-compatible
patch, changed file hashes, test logs/JSON, screenshots, URL specification, matrix,
restoration/preservation evidence and SHA-256 manifest. Dependencies, runtime caches,
.git, secrets and temporary services are excluded. Historical report contents remain
historical, not new validation claims. All previous checkpoints remain intact.

Verify the external ZIP SHA-256; extract into a new isolated directory; verify every
MANIFEST.sha256 entry. The supplied patch is also applied to the exact V1.6 git
archive and compared byte-for-byte with the delivered complete tree by the packager.
No command in this document authorizes host or production execution.

One recommendation for V1.8: add a compact summary of the applied criteria, readable
by analysts and copyable with the view link, without persisting financial results.
