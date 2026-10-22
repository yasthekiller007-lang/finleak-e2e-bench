# FINLEAK Product V2.0 — Personal named exception views

Development checkpoint from exact V1.9 `277511d0fdb043f850db176bf836fcffbfa4937e`.
Work is confined to an isolated Cloud development branch. No PC execution,
GitHub Actions, paid resources, native database, OIDC bypass, production deployment
or financial rule change.

## Implemented behavior

**My saved views** is integrated into the existing server exceptions queue.
Members can save an acknowledged search, find and page through their personal
views, re-open a view, rename it, explicitly replace its criteria and confirm its
deletion. The panel lists the current route's type; Human review views are managed
on `/review`, and anomaly views on `/anomalies`. Both types share the quota.

The live gateway uses authenticated BFF routes. Only the dedicated demo adapter
uses memory, with a persistent on-screen synthetic warning. It never uses browser
storage and is never a fallback for a failing live service. Its state resets when
the demo gateway is recreated. Native persistence has **not** been demonstrated.

Saving uses the existing `AppliedCriteria` only after a successful query. It is
blocked while criteria change, a read is pending or failed, authorization is absent,
the snapshot is invalid, or the applied URL does not represent the same criteria.
The handler also checks the existing synchronous pending-edit guard. The name form
revalidates the current snapshot at submission; opening a form does not pin a stale
draft. A synchronous operation guard prevents duplicate personal-view submissions.

A successful write is shown only after the API response. No optimistic local save
is presented as a backend save. Explicit criteria replacement and deletion each
require a separate confirmation. Renaming sends only the name and expected revision.
A conflict retains the draft and blocks further writes until explicit re-reading.
A lost write response is treated as an uncertain outcome; it is never replayed
automatically. Re-reading can recover the recorded view, without asserting that a
failed response itself proved persistence.

Opening first fetches the view by ID from its authorized API, checks its owner,
organization, type, format and criteria, then uses the existing V1.7 decoder and
queue `change` transition. Cursors reset, a fresh query starts on the first page,
and the existing successful-read callback updates the V1.7 URL. Even an identical
view starts a fresh read. Failed reads retain the last acknowledged URL. Results
and decisions may have changed; no historical financial results are restored.
Unavailable sources remain exact constraints and are never substituted or silently
removed. Dynamic `current`/`needs_review` searches still have the 100-candidate limit.

## API contract

Prefix: `/api/v1/organizations/{organization_id}/financial/saved-views`.
BFF prefix: `/api/organizations/{organizationId}/financial/saved-views`.

| Method | Suffix       | Request                                                | Result                         |
| ------ | ------------ | ------------------------------------------------------ | ------------------------------ |
| GET    | empty        | Optional `search`, `view_type`, `limit`, `after`       | Bounded personal page          |
| POST   | empty        | Name and complete definition                           | 201, authoritative record      |
| GET    | `/{view_id}` | No owner supplied by browser                           | Current personal record        |
| PATCH  | `/{view_id}` | `expected_revision` and exactly one of name/definition | Updated record, revision + 1   |
| DELETE | `/{view_id}` | JSON `expected_revision`                               | Deleted ID and `deleted: true` |

Example creation body (synthetic criteria, no results):

```json
{
  "name": "CFO USD review",
  "view_type": "anomalies",
  "format_version": 1,
  "criteria": {
    "supplier": "AcmeCloud",
    "currency": "USD",
    "sort": "newest",
    "needs_review": false
  },
  "page_size": 20
}
```

The backend derives `user_id` from `AuthorizedOrganization`, which uses the existing
OIDC verification, identity mapping, active-user, active-tenant and current membership
dependencies. Browser `user_id`/`organization_id` body fields are rejected.
All SELECT/UPDATE/DELETE queries include both organization and owner; an inaccessible
record returns 404. Any current member role may manage their own views; this conveys
no authority to make financial decisions. Identity, membership and financial policies
are unchanged. Reads re-check membership through the dependency on every request.
Writes additionally lock and re-check the membership row, fencing membership deletion.
No foreign key to membership blocks later revocation: retained rows become inaccessible
when membership is lost. Re-granted membership can restore access to that user's rows.
No public or collective sharing is added.

The page contains `items`, `limit`, `has_more`, `next_after`, `max_views: 50`.
API limit is 1–20, default 10; the browser requests 10. `after` is a personal-view UUID,
not a financial search cursor. Ordering is immutable UUID ascending, and continuation
uses `id > after`; renaming never reorders pages. Search is a bounded, escaped LIKE
query on normalized names. Unknown/repeated list parameters are rejected. Concurrent
inserts before the anchor may appear only after restarting the list; deletion may
shorten a page. This is a fresh list, not a transaction-wide snapshot or exact count.

Names are NFKC-normalized, whitespace-collapsed, trimmed and limited to 80 Unicode
characters. Empty names, controls, format/bidi controls and surrogates are rejected.
The equality key is Python Unicode `casefold()` of that name (up to 240 characters),
stored with PostgreSQL C collation. Uniqueness is per organization/user/view type.
`Straße` and `STRASSE` therefore collide; equal names in another type do not.
Supplier strings keep the existing exact snapshot semantics and are not name-normalized.
The demo's advisory lowercase comparison is not proof of the backend's Unicode
casefold/uniqueness behavior; backend pure tests cover the authoritative normalizer.

Definition format 1 stores only the existing approved Filters fields, including sort,
with a separately allowed page size (20/50/100). The strictly synthetic demo additionally
allows page size 2. Validation layers strict wire types and an extra-field prohibition
on the existing backend `Filters`, with approved outcome enums, UUIDs, safe text,
timezone-aware creation dates, ordered bounds and missing-contract incompatibility.
Boolean strings/numbers, arbitrary nested objects and null criteria are rejected.
Missing `needs_review` is filled from the route type: true on review, false on anomalies;
an explicit false override is preserved. Unknown stored formats/fields are rejected
on reading, rather than silently cleaned. Frontend validation is additional protection,
not the authority. The backend validates structure; it does not certify that a client
actually executed an earlier successful search. No signed query-receipt protocol exists.

Errors retain existing JSON envelopes and correlation/no-store conventions: 401 for
no session, hidden 404 for inaccessible organization/owner/record, 422 for invalid
input/format/type, and 409 for duplicates, quota or stale versions. Backend writes
are streamed with a 16 KiB bound, strict duplicate-key JSON handling and 30-second
receive limit. BFF writes enforce server session, allowed route/method, exact configured
Origin, JSON type, 16 KiB body limit and a bounded upstream request. Browser bearer
headers are ignored. Server tokens and cookies are never part of personal-view payloads.

## Candidate persistence and migration

`0010_personal_saved_views.py` follows `0009` and creates only
`saved_exception_views`. It has UUID identity, existing organization/user foreign keys,
name/key/type, versioned JSONB criteria, page size, timestamps, optimistic revision
and an internal quota slot. There is no business-data cascade. Downgrade refuses to
discard non-empty personal views. No historical migration is modified.

A unique `(organization_id, user_id, slot)` with non-null integer slots 1–50 puts an
at-most-50 constraint in the schema independently of a count/check race. The repository
serializes personal writes on the current membership row and allocates an unused slot.
A uniqueness failure returns 409 rather than overwriting. All types share the same slots.
The unique normalized-name key prevents duplicates in the specified scope. JSONB is
constrained to an object and 4 KiB serialized text; the server schema is the field/value
allowlist. The database constraints alone are not a substitute for that API validation.

Updates and deletes use owner/organization/ID/revision predicates in the mutation
statement. Stale revisions are rejected. Updates increment a bounded safe-integer
revision; the route commits before returning success. A failing commit cannot produce
a successful acknowledgment. A disconnected client does not prove server rollback;
re-read before another explicit write.

The existing unique indexes cover the organization/user prefix; each scope has at
most 50 rows. No additional performance migration is justified by this change.
No native planner, lock, race, restart or latency result is claimed. A future authorized
migration also needs the established application DB role to receive CRUD only on the
new table; this checkpoint changes no live roles or grants, and does not qualify them.
The candidate SQL is emitted offline for review, not applied to any database.

## Isolation and data minimization

No new financial model or query engine is introduced. Financial API, calculations,
Decimal/Numeric handling, currency separation, authoritative decisions, reasons,
409 behavior, audit, source associations, proofs/citations, signed cursors and dynamic
limits remain unchanged. The new repository mutates only its personal table. Backend
integration changes register that model/router/body guard and allow PATCH/DELETE for
existing configured CORS origins. Existing route methods/authorization stay enforced.
No Recovery Ledger work is performed.

Only criteria are stored, with no result page, potential amount, case count, individual
decision/reason, quotation, source file copy, token, cookie, pagination cursor or URL.
Current document labels are not persisted; missing labels are displayed as unavailable,
not invented references. View names and search strings can themselves contain sensitive
business text: this is schema minimization, not a DLP filter or new encryption promise.
URL copying remains separate and retains its existing privacy warnings/access caveats.

## Actual development verification

| Check                                                             | Actual result                | Scope                                                                                      |
| ----------------------------------------------------------------- | ---------------------------- | ------------------------------------------------------------------------------------------ |
| Frontend Vitest                                                   | **437 PASS, 35 files**       | 371 unchanged historical tests + 66 new, unchanged optional Cloud wait profile             |
| Backend targeted pytest                                           | **371 PASS**                 | 294 historical tests + 77 new validation/SQL/API-double tests                              |
| TypeScript, ESLint, Prettier                                      | PASS                         | Existing strict checks, no warning suppression                                             |
| Next.js optimized build                                           | PASS                         | Actual webpack build including new BFF routes                                              |
| Ruff / Python format                                              | PASS                         | 184 backend files formatted                                                                |
| Candidate migration                                               | PASS, offline contract       | Metadata/DDL constraints compiled, no DB application                                       |
| Browser                                                           | Actual synthetic application | Save by Enter, rename, explicit update, source-preserving removal, fresh first-page reopen |
| OIDC/PostgreSQL E2E                                               | **BLOCKED**                  | No new investigation or simulated native PASS                                              |
| Native migration, persistence/restart, grants, races, performance | **NOT VERIFIED**             | No native database execution                                                               |

All original test files and V1.7–V1.9 URL/summary/removal contracts remain byte-identical.
The optional, unchanged V1.9 Cloud test profile supplies one worker, 5-second async
UI waits and a 15-second per-test budget. This is not a one-second latency guarantee.
Tests with authorization dependencies, repositories, fetch and financial gateways
replaced by doubles are explicitly development/contract tests, not OIDC/PostgreSQL E2E.
Initial failures are retained: a new DDL test initially omitted the real Alembic metadata
naming convention; a new component test used the wrong existing unavailable-label text.
An unused type import and a render-time ref access were found by TypeScript/lint and
corrected before release. A visual review also found a stale waiting message after opening a view; it now directs the user to the queue result without claiming a pending or successful financial read. No historical test or assertion was relaxed.

Coverage includes validation/normalization, quota slots and duplicate failures,
scoped parameterized bounded SQL, keyset list order, membership re-check, API ownership,
strict body guards, rename vs replacement, CAS conflicts and rollback, exact candidate
DDL constraints, coherent snapshot gating, confirmation, double submissions, explicit
retry/re-read, uncertain write outcomes, stale replies, organization/user changes,
source unavailability, first-page fresh reads, defaults and financial write exclusion.

Reproduce in an isolated authorized development checkout using existing lockfiles:

```text
frontend: npm run typecheck
frontend: npm run lint
frontend: npm run format:check
frontend: NEXT_TELEMETRY_DISABLED=1 ./node_modules/.bin/next build --webpack
frontend: ./node_modules/.bin/vitest run --config vitest.product-v19-cloud.config.ts
backend: <locked-development-venv>/bin/python -m pytest -q tests/test_money.py tests/test_financial_engine.py tests/test_proof_canonical.py tests/test_proof_assembly.py tests/test_oidc_transport.py tests/test_product_v11_development.py tests/test_product_v13_context.py tests/test_product_v14_query.py tests/test_product_v15_facets.py tests/test_product_v16_invoice_facets.py tests/test_product_v20_saved_views.py
backend: <locked-development-venv>/bin/ruff check .
backend: <locked-development-venv>/bin/ruff format --check .
```

## Remaining limits

OIDC/PostgreSQL E2E remains **BLOCKED**, without renewed infrastructure investigations.
Migration application, native PostgreSQL persistence/restart, concurrency, real grants,
query plans and performance remain **NOT VERIFIED**. Native acceptance must later use
synthetic members in an independently authorized compatible Cloud database and issuer;
no current artifact authorizes that execution. Screen captures show only the actual
compiled synthetic app. Exhaustive screen-reader/mobile certification is not claimed.
No sharing, team views, defaults-on-login, server historical result snapshots, quotas
per enterprise plan, offline writes or durable browser storage are implemented.

Phase 7/PITR/ClamAV: **NOT QUALIFIED**. Scanner: **BLOCKED**. Pilot: **NO-GO**.
PC and production: **NOT AUTHORIZED**.

## One recommendation for V2.1

Add an explicit comparison between a selected saved view's criteria and the current
acknowledged search before confirming replacement, so analysts can see exactly what
will change without storing or comparing financial results.
