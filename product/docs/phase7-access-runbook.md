# Controlled access and identity acceptance

This procedure requires a separately approved environment, enrollment and attributed operator session. No tenant has been provisioned by this task. No public invitation or privilege-grant API exists. Local access control does not claim global IdP logout, instant JWT revocation or legal deletion.

## Operator changes

Use the separate roster DB principal in the [deployment contract](phase7-deployment-runbook.md). Users must first complete genuine verified sign-in; issuer/subject matching never uses email similarity. The journal records the known operator user UUID, purpose, server time, request UUID, target IDs, old/new role or availability and actual database principal/effective role. It excludes names, email, source content and money. FinancialAudit remains separate financial history.

Every CLI mutation requires `--actor-id UUID --reason 'approved purpose' --apply` before the subcommand. These are placeholders, not commands run against a customer environment. Never pass database URLs/passwords/tokens as command arguments.

```sh
uv run python -m app.admin --actor-id ACTOR_UUID --reason 'Approved enrollment' --apply create-organization --name 'Approved company'
uv run python -m app.admin --actor-id ACTOR_UUID --reason 'Approved owner' --apply grant-membership --organization-id TENANT_UUID --issuer ISSUER_HTTPS_URL --subject VERIFIED_SUBJECT --role owner
uv run python -m app.admin --actor-id ACTOR_UUID --reason 'Approved role change' --apply grant-membership --organization-id TENANT_UUID --issuer ISSUER_HTTPS_URL --subject VERIFIED_SUBJECT --role analyst
uv run python -m app.admin --actor-id ACTOR_UUID --reason 'Approved transfer' --apply transfer-owner --organization-id TENANT_UUID --previous-user OLD_OWNER_UUID --new-user ENROLLED_RECIPIENT_UUID
uv run python -m app.admin --actor-id ACTOR_UUID --reason 'Approved revocation' --apply revoke-membership --organization-id TENANT_UUID --issuer ISSUER_HTTPS_URL --subject VERIFIED_SUBJECT
uv run python -m app.admin --actor-id ACTOR_UUID --reason 'Approved user offboarding' --apply deactivate-user --user-id USER_UUID
uv run python -m app.admin --actor-id ACTOR_UUID --reason 'Approved tenant offboarding' --apply offboard-tenant --organization-id TENANT_UUID
```

Enroll the initial owner before admitting users/traffic. Transfer requires a distinct existing active enrolled recipient: it establishes the recipient as owner before demoting the prior owner to admin. Changes, revocation and user deactivation cannot remove the active tenant’s last owner. There is no automatic replacement. Deactivation waits for current protected authority, removes memberships and persists unavailability; a new grant cannot reactivate access. Tenant offboarding freezes access before removing its entire roster, including owners, under explicit operator authority. Reactivation, data deletion/legal holds and backup erasure require separate reviewed actions. No retention duration is invented.

Shared user locks precede tenant/membership locks. Ordinary app credentials cannot mutate roster, availability, stable IDs or operator history. Non-superuser roster mutations require attribution and database last-owner protection. Privileged migration/CI fixture mutations retain actual DB principal and an explicit unattributed-review marker when no actor context exists; those are not complete human attribution for pilot operations.

IdP disablement remains a separate externally verified action. App logout clears the session; an issued offline-valid JWT may remain cryptographically valid until expiry. Current local revocation/deactivation still blocks it. Offboarding includes ingress/work suspension, IdP/roster review, history/originals/backups inventory and reviewed deletion/legal hold escalation. It does not delete, recalculate or approve financial history.

## OIDC staging acceptance

Every actual-provider result below remains **IMPLEMENTED / EXTERNAL EVIDENCE PENDING** until an authorized deployment with the actual issuer is tested. Current JWT/discovery/session/proxy/roster tests are engineering evidence. The approved audit remains unchanged; these user-requested labels state execution cases explicitly where historical audit labels differ.

| Case | Required actual-provider evidence | Engineering boundary |
| --- | --- | --- |
| OIDC-01 login | Normal confidential-client issuer redirect/login and approved roster | Genuine asymmetric token, issuer/subject; no email linking/header bypass |
| OIDC-02 callback | Registered exact HTTPS callback; PKCE/state/nonce and redirects tested | Existing NextAuth OAuth path; browser protocol acceptance in checkpoint H |
| OIDC-03 logout | App cookie cleared; protected UI denied; IdP SSO behavior recorded | No offline-token/global-provider revocation claim |
| OIDC-04 session expiry | Expired session/API token rejects; explicit re-login works | Exp/iat/nbf and session limits; no implicit refresh |
| OIDC-05 invalid token | Malformed/unsigned/wrong signature/ID token denied safely | `test_identity.py` required claims and negative tokens |
| OIDC-06 wrong audience | Genuine other-client/API token denied | Configured issuer/audience/algorithms; token jku ignored |
| OIDC-07 key rotation | Actual issuer publishes/retires keys; bounded cache behavior recorded | Configured discovery/JWKS; no token-directed URL/fallback identity |
| OIDC-08 membership revocation | Same valid token loses authority after committed revocation | Fresh roles, transaction fencing and PostgreSQL races |
| OIDC-09 disabled user | Actual IdP disable blocks login; local disable blocks existing token | Persisted local unavailability tested; provider semantics require observation |
| OIDC-10 provider outage | Discovery/token/JWKS faults produce safe errors; cache behavior recorded | No test identity fallback or raw issuer/credential errors |

Record exact release SHA, safe configuration references, times, cookie/header observations and case outcomes in a restricted staging record. Synthetic accounts only; no JWTs, cookies, credentials or customer evidence in traces/logs. No provider or deployed identity integration is claimed here.

## Bounded identity transport

`auth/oidc.py` shares bounded discovery/JWKS reads: 512 KiB actual decompressed JSON per response, five-second socket/work profile and at most 100 distinct identified keys. Redirects, URL credentials and token-directed key URLs are rejected; unexpected environment proxy routing is disabled. HTTPS is required outside loopback engineering. Malformed, oversized or unavailable responses fail closed without provider text in errors. These are engineering safeguards, not measured provider latency/availability claims.

The existing five-minute key cache and locked PyJWT 30-second unknown-key refresh cooldown remain explicit. Newly published keys can be rejected until refresh is permitted; the issuer must prepublish/overlap keys appropriately. Cached valid keys may verify during an outage until cache expiry. Logout/issuer disablement does not imply immediate offline-token revocation. `test_oidc_transport.py` uses real HTTP and RSA signatures for configured/discovered keys, rotation/retirement, unknown-key throttling, cache expiry/outage, response bounds and production HTTP rejection. Test clock advancement models expiry/cooldown; it does not qualify a real issuer.
