# First execution — precise review and authorization boundary

**P0-D1 addendum:** the first run already occurred as `39851915526` (FAIL before
E2E). Its post-run balance was 995 minutes with $0 displayed and the $0 blocking
budget retained. These are historical observations, not a new billing assessment.
This branch only remediates diagnostics. A second run, any default-branch merge,
and the new immutable candidate SHA require separate review/authorization; see
`DIAGNOSTICS-D1.md`. The original first-run preparation instructions below remain
historical. Do not dispatch, rerun, modify budgets or reuse stale gate evidence.

**Do not dispatch now.** The scope of the reported `Usage blocked` label is unverified,
so admission remains blocked. Distinguish blocked chargeable overages from an
actual prohibition on the proposed included-quota job. Neither interpretation is
proved by a remaining-minutes figure alone.
Do not change a budget, payment method, spending cap or account protection to make
this candidate run. A new billing cycle or clarified account evidence may change
availability; remaining minutes alone are insufficient. No zero-cost guarantee is
claimed by this preparation.

## 1. Supply authenticated evidence before requesting a run

The authorized owner must review GitHub Settings → Billing and licensing / usage,
Actions usage, storage and every applicable owner/org/enterprise budget. Interface
labels may vary. Required evidence, with payment details and secrets redacted:

- Exact owner and existing private bench repository; write/dispatch permission for
  one named GitHub actor; standard ubuntu-24.04 runner permitted by all policies.
- Current billing-cycle dates, timestamp, remaining minutes (≥10), storage headroom
  and other concurrent or queued account usage. Record freshness within 24 hours.
- Effective applicable **blocking** spending controls, with extra-charge prevention
  independently established, including first-budget-cycle and delayed-update caveats.
- An authenticated observation establishing that Actions usage is permitted. If
  the proposed included-quota job is actually blocked, or label scope remains
  unresolved, stop. If authenticated evidence shows the label only blocks paid
  overages while the included job is permitted, retain that distinction and the
  protective $0 cap. A JSON boolean cannot override the account.

Store a redacted export outside the source and compute its SHA-256. Only after the
facts are independently reviewed, fill `billing-evidence.json` from the example.
`usage_blocked` means an effective block on this proposed job, not a literal copy
of a billing badge. The reported badge is retained separately in the example.
Every `true` value is a review assertion supported by that export; the script checks
its scope/hash/freshness, **not authenticity or current billing state**. Never paste
a password, PAT, signing key, payment detail or token into a file or conversation.

GitHub documents budget reporting/first-cycle caveats; a $0 alert without effective
blocking protection is insufficient. If prevention of additional charges cannot be
established under existing controls, this first run remains BLOCKED.

## 2. Prepare the separate repository content without changing FINLEAK main

The workflow must exist on a repository's default branch for initial manual dispatch.
Do not put it on FINLEAK main to satisfy this requirement. Use an already authorized
private bench repository with a dedicated default branch such as `bench-p0`.
Its existence, default branch and permissions are presently NOT VERIFIED. Creating
a repository or changing its default branch requires separate authorization.

The supplied `bench-repository/` projection is reviewable local content only:

```
.github/workflows/finleak-p0.yml      # the sole active, manual-only workflow
product/                           # complete frozen V2.3 + isolated P0 additions
product/.github/workflows/ci.yml    # preserved historical bytes, nested and inactive
PROJECTION.json                    # hashes and exact P0 source commit
```

To regenerate it in an authorized isolated Cloud checkout:

```bash
python bench/p0/prepare_repository.py --output /absolute/new/cloud/bench-payload
```

No git init, remote write, push, PR or dispatch is performed by this script. Importing
the projection into the chosen repository is a separate write action requiring
authorization. Do not push the product checkout's old workflows at repository root:
the historical CI includes automatic triggers and multiple jobs.

After an authorized import, review the sole active workflow, repository protections,
visibility, exact Git commit, payload hashes and fresh billing evidence. The commit
to approve is the **bench payload commit**, which differs from product V2.3/P0 commits.

## 3. Request exactly one bounded authorization when all prerequisites pass

The request must specify: existing private repository; actor; dedicated default
branch; full reviewed payload commit; SHA-256 of `billing-evidence.json` and its
authenticated redacted export; confirmed unblocked execution and effective zero-
extra-charge controls; one ubuntu-24.04 job; maximum ten minutes; no rerun/retry;
synthetic data only; migrations through 0010 in the disposable database only;
no production, scanner, paid resource or Phase 7 qualification.

No authorization request is issued in this checkpoint because billing availability,
effective spending protection and the target repository are not yet established.

## 4. Only after that separate authorization, perform one manual dispatch

In the approved private repository: **Actions → FINLEAK P0 synthetic OIDC PostgreSQL
acceptance → Run workflow**. Select the approved default bench branch and enter:

- `authorization`: `FINLEAK-P0-ONE-RUN` (a review marker, not a credential or approval).
- `expected_commit`: exact reviewed 40-character **bench payload** commit.
- `billing_evidence_sha256`: exact 64-character hash of the root review file.

Click Run workflow once. No automatic trigger, retry or second attempt is authorized.
If blocked, cancelled, failed, timed out or incomplete, preserve the logs and stop.
Do not raise caps, change machine size, grant privileges or rerun to obtain green.
GitHub job scheduling occurs **before** in-job checks and can consume minutes even
if a guard fails; therefore cost/permission approval must happen before this click.

## 5. Review evidence without publishing or creating storage artifacts

Download the authenticated job logs and retain run ID, actor, commit, runner image
metadata, timestamps, duration and conclusions. `emit_evidence.py` prints one JSON
line per finite receipt with filename, base64 and SHA-256. Decode each `base64` value,
hash the bytes and compare the advertised SHA; retain `FINLEAK_P0_MANIFEST` as the
manifest. A job conclusion alone is insufficient: browser and independent SQL
witness must exist, with restart/reread, 201/409 and expected Decimal invariants.

Absent receipts, incomplete cleanup or job timeout cannot be interpreted as PASS.
No artifact upload is configured. Keep all records private and redacted. Any native
grant/migration/provider failure is evidence to review, not permission for fallback.

Primary documentary sources checked 2026-10-22:

- https://docs.github.com/en/actions/reference/runners/github-hosted-runners
- https://docs.github.com/actions/managing-workflow-runs/manually-running-a-workflow
- https://docs.github.com/en/billing/concepts/budgets-and-alerts
- https://docs.github.com/en/billing/how-tos/set-up-budgets
- https://hub.docker.com/_/postgres
- https://www.python.org/downloads/release/python-31215/

Resource/time feasibility is a bounded design estimate; no future runner has been
qualified by producing this configuration.
