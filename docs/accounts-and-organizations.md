# Accounts and organizations

Credential operations use one persistent implementation in `accounts/request_budget.py`.
The existing counter table and registration HMAC namespace are preserved. Registration
remains 10 attempts per peer per 10 minutes; local login permits 240 attempts per peer
and 60 per peer/account in the same window. Counters commit before credential handling,
so rejected passwords and later business rollbacks cannot reset them. A 4,096-key
admission limit is serialized with a PostgreSQL transaction advisory lock or SQLite's
write lock. Counter keys never contain raw addresses, emails or passwords. Cross-site
local login is rejected; authentication and business API responses use `no-store`.

PostgreSQL downgrade takes bounded exclusive locks before checking membership
cardinality, preventing a concurrent join between the preservation check and table
removal. Use a quiesced, backed-up maintenance environment; lock contention fails
within five seconds. Never use downgrade to erase additional organizations.

X-Pharma separates global identity from organization authorization. A human
session selects exactly one organization. Joining another organization never
moves, merges or shares the original organization's facts, collections,
subscriptions, exports, preferences or audit history.

## Single authorities

- `models/accounts.py`: `User` owns credentials, issuer/subject, global profile
  and identity revocation version. `home_tenant_id` is a login preference, not an
  authorization boundary. `OrganizationMembership` owns each organization's
  role, suspension, revocation version and last login.
- `accounts/access.py`: reads live administrator authority. Administrative
  mutations recheck that authority after acquiring the organization lock.
- `accounts/service.py`: issues, revokes and atomically claims email-bound,
  expiring, single-use invitations. An invitation does not grant membership
  until the intended identity explicitly accepts it. Invitations grant analyst,
  never administrator, membership.
- `security.py`: verifies signed sessions against the stored session, global
  account version, membership version and current organization/account status.
  Roles come from the database, not from a client header or JWT role claim.
- `db.py`: applies signed organization context and a domain-separated signed
  account context. PostgreSQL account context permits reading only the
  identity's membership catalog. Business reads and membership writes remain
  organization-scoped; a catalog signature is not a cross-organization grant.
- `http/`: owns transport, origin checks, cookies, request bounds and response
  policy. Feature routers do not import the application bootstrap. HTTP settings
  share one injectable binding to the canonical configuration cache.
- The web session boundary owns the selected identity. Each account,
  organization and role context gets an independent workspace query client.
  Late callbacks can modify only the old client's cache. Tables consume the
  same React session context instead of inferring identity from a feature cache.

## Registration and invitation acceptance

In local development mode, external researchers can register an independent
viewer account when self-registration is enabled. New internal accounts require
an administrator-issued invitation. An existing identity instead uses the
authenticated **组织与账号** menu or the **加入组织** login entry, verifies its
existing credentials and explicitly accepts the invitation.

Membership in the destination is not created merely because an administrator
issues a code. The code is bound to the account email and checked for expiry,
revocation, prior use, active organization and an active sponsoring
administrator. An existing suspended membership must be restored by that
organization's administrator; a new invitation cannot overwrite its role.

OIDC identities are linked by verified issuer and subject. For an existing linked
identity, an IdP tenant claim is not an application membership grant and does not
overwrite the chosen organization. First-time auto-provisioning, if explicitly
enabled, still requires an active recognized organization and verified email;
it cannot provision an administrator through a role claim.

An existing linked OIDC identity can explicitly accept an invitation even when
its original organization membership is suspended. The invitation transaction
is MAC-protected in an HttpOnly cookie, bound to OAuth state, nonce and PKCE.
The invitation is not placed in the IdP redirect URL. The callback requires the
linked, verified enterprise email and revalidates the invitation before claiming
it. Deployments must configure their real IdP to supply these verified claims;
the local protocol tests do not attest a production IdP configuration.

## Session and browser behavior

`POST /api/v1/auth/login` can accept an optional organization ID. Without one,
the service chooses an active home membership or another active membership; it
never creates a membership during login. The authenticated organization catalog
includes only memberships belonging to that identity.

Switching requires active membership and issues a new session and CSRF cookie.
Only the switching device's old session is revoked. Other devices can retain
their independently chosen organizations. A role change or suspension increments
the destination membership version and revokes sessions in that organization,
not in the account's other organizations.

A password change increments the global identity version. It renews the current
cookie and invalidates old sessions in every organization. Profile fields are
global identity data; organization last-login activity is not shared as a global
administrative activity timestamp.

Protected browser requests bind the expected account and organization using
`X-Account-ID` and `X-Organization-ID`. The server rejects a mismatched session
with 409 and `X-Session-Context: changed`; neither header grants access. This
prevents a stale tab's action from silently targeting a new shared-cookie
context. Identity confirmation itself is a neutral authenticated read.

The UI pauses, cancels reads and evicts protected caches during switching. It
waits for an authenticated confirmation before reopening. An ambiguous network
failure stays paused with an explicit retry; old cached data is not reopened as
if the switch had failed. In-flight writes block a same-tab switch. Other tabs
reconfirm after a context-change notification or when they regain focus.

## Preservation migration

Revision `d32a6c1f9e74` follows the released account-registration revision. It
copies each legacy role, suspension, token version and organization login time
into the account's original membership, retains every user UUID and credential
hash, and rewires organization-context foreign keys. Existing business owners,
sessions, group members, invitations and table preferences retain their IDs and
organization boundaries. The legacy organization suspension becomes membership
suspension; it does not become a permanent global identity ban.

Apply only through the reviewed deployment maintenance procedure, with a
verified backup and an exact source/image candidate. Do not run old application
code against the new schema. The migration/provisioning commands validated in
the isolated PostgreSQL contract environment are:

```sh
uv run alembic upgrade head
uv run alembic check
uv run pharma-db-provision
```

Legacy stored sessions remain valid only in their migrated original membership
and until their original expiry. New sessions carry both account and membership
versions. No old session can be reused to enter an additional organization.

Downgrade refuses accounts with additional or incompatible memberships. It must
not erase new organizations to make old software run. After multi-organization
writes, prefer a forward fix. Restoring an older database backup would discard
post-backup writes and requires a separate preservation and recovery decision.

## Regression evidence and boundaries

Behavior tests cover real cookie/CSRF authorization, explicit consent, unchanged
identity IDs, switching, revoked old cookies, organization-specific suspension,
global password revocation and preservation of private research. PostgreSQL
tests use a disposable non-superuser/non-bypass-RLS role, verify catalog and
business isolation, check the actual RLS permission error with valid foreign
keys, and race concurrent invitation claims.

The controlled loopback OIDC authority uses real HTTP code exchange, PKCE, JWKS
and RSA parsing. Four viewport browser scenarios verify membership acceptance,
refresh, cross-tab coherence, private collections, switch-back and logout.
These checks do not certify a real production IdP, licensed datasets, production
HA, billing authorization or a paid model provider.

Session/workspace tests and the full project gates must run against the exact
release candidate. A partial diagnostic run or a snapshot-update run is not
release evidence. Do not retain credential or invitation screenshots/traces.
