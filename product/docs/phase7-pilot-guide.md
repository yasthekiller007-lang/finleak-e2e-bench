# Controlled pilot guide

This guide describes the implemented workflow. Customer pilot use is **NO-GO** until the blocking gates in the validation report have evidence and separate approval. It is not a deployment instruction or a financial certification.

## Enrollment and scope

An authorized operator enrolls verified issuer/subject identities and a named company through the access runbook. Email alone does not establish membership. There is no public signup, self-service role grant or anonymous evidence access. Confirm the organization and current role on every task. Viewers read; analysts prepare and scan; owners/admins release originals and make final authority decisions. Application sign-out ends its session; provider SSO and issued token expiry/revocation follow the access runbook.

The initial scope is one enrolled company, manual document intake and explicit deterministic review in Chromium. Use passive PDFs, UTF-8 CSVs or supported XLSX within the displayed upload limit. Scanned PDFs need OCR and cannot supply invented text; OCR, automatic matching, inbox connectors, FX, complex pricing, accounting integration and autonomous recovery remain outside this pilot. Formulas are not executed. Unknown or unsupported facts remain blocked/unassessed, never a known zero.

## Walkthrough

1. Open Documents and choose the correct organization and document type. Upload the original, retaining its filename and exact bytes. Duplicate notices refer to preserved source identity. Unsupported inputs require a corrected source or manual clarification.
2. Open the document. Enter a source action reason and scan the exact original. A clean scan requires separate owner/admin release. Failed, unknown, infected, suspicious or timed-out scans keep processing and original download blocked. Clean does not guarantee absence of threats. Refresh status before retrying a failed action.
3. Release the current clean scan deliberately, then explicitly process. Neither scan nor release runs extraction or financial workflows. Inspect candidates, warnings, raw values and source locations. Previous processing versions remain available. A candidate is not approved authority.
4. Open Contract and invoice review. Create a stable source review; prepare terms, billing scope, packet/amendment completeness and the invoice association with exact source evidence. Manual evidence requires an explicit locator, quotation, meaning and resolved uncertainty. An owner/admin separately verifies and approves the current predecessor. Revocation preserves history and can block new positive authority.
5. Explicitly evaluate the approved invoice scope. Read contracted, billed, discrepancy and potential amounts in their original currency and tax basis. A blocked amount is not assessed. Finding confirmation is a separate decision; it never changes calculated amounts. Read notices describe reads, not saved approval. Limited pages do not establish complete totals.
6. Open the proof workspace. Generation is explicit; inspect all C01–C10 components, availability/currentness and canonical fingerprint. COMPLETE proof supports review but does not establish cash recovery. Optional approval/export is separate. Missing or altered original bytes can make new positive actions unavailable while preserving canonical history.
7. Open Recovery. Create a case, prepare party/readiness evidence and distinct economic instruments, then obtain owner/admin approval. Validated V, pursuit B, claim C and acknowledgement S are different facts. Issued but unapplied credit is pending; it contributes no realized R. Approved partial cash and actually applied credit contribute their supported amounts. Net cash N is separate; costs are separate and never netted into R. No button submits a claim or moves funds upstream.
8. Use append-only reversals/corrections and explicit reasons. Review economic dates separately from the report's known-at timestamp. Historical reports use captured PostgreSQL commit provenance; restore cannot invent historical knowledge. Revoked, stale and dismissed records remain auditable. Closure is a management fact, not a cash event.

## Errors, support and offboarding

Keep the safe request ID and action/time/organization for support; do not send raw bank details, tokens or customer evidence into logs or chat. A lost response is not proof of failure: refresh current state before retrying the same unchanged command. Changing a reason or predecessor is a new request. Do not repeatedly submit while busy. Rate limits include safe retry guidance; service outage requires operator investigation. There is no automatic mutation from a refresh.

Operators use the deployment, access, incident and backup/restore runbooks. Offboarding revokes local membership and provider access, verifies old-token denial and preserves authoritative evidence/history. Return/deletion, legal holds and backup retention require separately reviewed instructions; no blanket erasure or retention duration is promised. Customer privacy, commercial limitations, support owners and deputy acceptance remain **EXTERNAL EVIDENCE PENDING**.

## Synthetic demonstration

Use only a disposable synthetic tenant, fictional `DEMO-*` sources and the approved specification's DEMO-01–15 script. All amounts are exact decimal strings in USD, tax exclusive, quantum 0.01. The existing financial and recovery worked-example tests are the authoritative executable examples; do not hand-write financial SQL or auto-approve real sources.

| Demonstration | Expected meaning |
| --- | --- |
| DEMO-01 | 100 × 10 = 1000, billed 1000: no positive potential |
| DEMO-02–04 | Unit price P=200; fixed cycle P=100; unconditional discount P=50 |
| DEMO-05 | Missing amendment/tax authority: null/blocked |
| DEMO-06–08 | Confirmed V=200, COMPLETE proof; B=150, C=150, S=100; R is still zero |
| DEMO-09–11 | Cash 60: R=60,N=60; issued credit 90 pending; applied 40: R=100,N=60,pending=50 |
| DEMO-12 | Cash return 20: R=80,N=40; historical known-at report preserved |
| DEMO-13–15 | Source failure/material revision blocks new positive authority; historical proof remains; cost 5 remains separate; dismissal is a category/history event |

Use independent reviewed settled instruments for independent receipts; never alter an instrument's raw cash fact to make a demonstration pass. Runtime/provider/browser/volume qualification is recorded separately from this script. No synthetic demonstration qualifies external staging or customer acceptance.
