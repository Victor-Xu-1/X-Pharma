# Commercial MCP operations

The PostgreSQL commercial ledger is authoritative. Do not create subscriptions, change balances, or repair settlements with ad-hoc SQL. Valkey and downstream billing systems are projections only.

## Before provisioning

1. Apply the Alembic migration with the migration identity.
2. Obtain an approved customer contract, data-license mapping, rate card, OAuth client ID, subject mapping, and change-ticket/operator ID.
3. Keep the Domain API private. Only the Web and MCP Gateway may be published.

The files `deploy/commercial/rate-card.schema-example.json` and `deploy/commercial/export-field-policy.schema-example.json` demonstrate the accepted schemas. Their prices, fields, filters, and attribution are examples, not approved production terms.

Each item can charge `base_units`, `per_result_units`, `per_kib_units`, and `per_compute_unit`. Chemistry exact/substructure/similarity use separate billing classes and reserve one fixed compute unit before the private Domain API runs. The reservation, full query arguments, result bound, billing class, and required compute units must all match. Never lower or rewrite a published price: publish a new rate-card revision and migrate the contract through the approved commercial change process.

## Publish a rate card

```bash
pharma-commercial --tenant-slug acme --actor CHG-12345 publish-rate-card \
  --file /approved-config/acme-rate-card-v1.json
```

The key and revision are immutable. Publishing the same content is idempotent; publishing different content under an existing key/revision is rejected. Use a new revision for any price change.

## Migrate a subscription to a published rate card

```bash
pharma-commercial --tenant-slug acme --actor CHG-23456 migrate-rate-card \
  --subscription-key acme-research-2026 \
  --rate-card-key acme-enterprise \
  --rate-card-revision 2 \
  --reason "Approved 2026 contract amendment"
```

The command locks the subscription, verifies currency and effective dates, synchronizes entitlement result ceilings, and writes audit and outbox records. It refuses to migrate while usage reservations are active, so every in-flight request is settled against the immutable rate card under which it was reserved. New entitlement categories inherit the strictest existing extraction controls; if existing domain policies differ, the migration fails closed and requires an explicit contract-policy change.

## Provision a client and subject

For production OIDC, use the verified client claim (normally `azp`) as `--oauth-client-id` and the verified token `sub` as `--subject-id`.

```bash
pharma-commercial --tenant-slug acme --actor CHG-12345 provision-client \
  --client-key research-agent-prod \
  --oauth-client-id 8f27c0a1-client \
  --display-name "Research Agent Production" \
  --actor-type agent \
  --subject-id service-account-subject \
  --account-key acme-main \
  --account-name "ACME Pharmaceutical" \
  --subscription-key acme-research-2026 \
  --rate-card-key acme-enterprise \
  --rate-card-revision 1 \
  --export-field-policy /approved-config/acme-export-fields-v1.json \
  --max-page-depth 10 \
  --daily-unique-record-limit 5000 \
  --max-response-bytes 2000000
```

For a development API key, use the API key identity printed by `pharma-bootstrap` as both the OAuth client ID and subject ID, with actor type `api_key`. Never store the secret itself in commercial tables.

The export field policy and three extraction limits are contractual controls. The policy must enumerate licensed output and filter fields per dataset and include a version and attribution. Re-running provisioning with different values is rejected; changing them requires an approved, audited command rather than direct SQL.

## Rotate or revoke export fields

```bash
pharma-commercial --tenant-slug acme --actor CHG-23456 set-export-field-policy \
  --account-key acme-main \
  --file /approved-config/acme-export-fields-v2.json
```

The update writes audit and outbox records. Any queued job or completed artifact whose stored policy version/hash no longer matches is denied; customers must create a new export under the current policy. A policy version referenced by an export job is immutable and cannot be reused after rotation. Removing a field from `fields` blocks delivery, and removing it from `filter_fields` also blocks inference through filtering.

## Cursor and coverage controls

- Keep `MCP_CURSOR_SIGNING_SECRET` independent from all JWT and tenant-context secrets. Rotate it as a coordinated breaking change because outstanding cursors become invalid.
- `search_entities` and `resolve_entity` accept only short-lived opaque cursors. A cursor cannot be reused by another tenant, subject, client, tool, query, or page size.
- Every settlement derives stable record identities from the durable server result. `commercial_coverage_records` counts exact first delivery per subscription, entitlement, day, and record type; it never stores the source payload.
- Active reservations consume conservative coverage capacity until settled, released, or expired. Do not increase limits to clear a stuck request; reconcile the reservation state.
- The human workspace commercial operations view is admin-only. It shows balances, clients, governed exports and deny events; it never exposes raw query text or private risk weights.
- Revoking a client requires a reason, releases active reservations, cancels pending/queued exports, requests cancellation for running exports, and writes audit/outbox records. Reactivation requires a second explicit reason.
- Risk cases move from open to acknowledged and then resolved/dismissed. Closed cases are immutable except for an idempotent replay of the same terminal status.

## Network and credential correlation

- Replace the fail-closed `MCP_TRUSTED_PROXY_CIDRS` sentinel with the exact Envoy Pod CIDR plus every trusted intermediary covered by `MCP_TRUSTED_PROXY_HOPS`. Never use a public catch-all CIDR. Envoy must discard caller-supplied forwarding headers and reconstruct `X-Forwarded-For` from its verified chain; NetworkPolicy must continue to deny direct MCP Pod ingress from other namespaces.
- Keep `MCP_CORRELATION_HMAC_SECRET` independent and stable. The database stores only HMAC values for the canonical `/24` IPv4 or `/56` IPv6 network and the signed OIDC confirmation key; raw addresses, `jkt` and certificate thumbprints are not persisted.
- `MCP_CORRELATION_KEY_ID` identifies the active HMAC generation. Coordinate rotation with security operations because a new generation intentionally starts a separate correlation window; retain old policy events for audit without retaining the secret.
- Production OIDC requires one signed `cnf.jkt` or `cnf.x5t#S256` claim. This application correlates that identifier but does not by itself prove key possession; Envoy/IdP must enforce DPoP or mTLS and that external integration remains a Production release gate.
- A network or credential rotation denial is handled like other commercial risk events: acknowledge the case, investigate the client and account, revoke affected clients when needed, and never increase thresholds merely to clear a denial.

## Grant prepaid units

```bash
pharma-commercial --tenant-slug acme --actor CHG-12345 grant-credit \
  --subscription-key acme-research-2026 \
  --units 100000 \
  --external-reference PO-2026-00421 \
  --reason "Approved annual prepaid allocation"
```

`--external-reference` is the idempotency key for a grant. Corrections require a separately approved adjustment or reversal record; existing grants and settlements must never be edited or deleted.

## Adjust and reverse usage

Every correction needs a unique approved key, operator identity, request ID and reason. `--units-delta` changes consumed units: a positive value is a debit and a negative value is a credit. The command rejects negative projected consumption and any debit that exceeds granted credit.

```bash
pharma-commercial --tenant-slug acme --actor FIN-INC-1042 adjust-usage \
  --subscription-key acme-research-2026 \
  --adjustment-key dispute-1042-debit \
  --units-delta 25 \
  --reason "Approved correction for under-billed usage"

pharma-commercial --tenant-slug acme --actor FIN-INC-1043 reverse-settlement \
  --settlement-id 00000000-0000-0000-0000-000000000000 \
  --adjustment-key dispute-1043-settlement-reversal \
  --reason "Confirmed duplicate upstream delivery"
```

A settlement can be reversed once. An adjustment can also be reversed once with `reverse-adjustment`. Both operations append a `billing_adjustment` and ledger entry; they never update the original record.

## Expire leases and reconcile

Run expiry before reconciliation. Both commands are safe to retry. Use a new `--run-key` when a fresh accounting snapshot is required; reusing a key returns the original immutable run.

```bash
pharma-commercial --tenant-slug acme --actor OPS-DAILY expire-reservations --limit 1000

pharma-commercial --tenant-slug acme --actor FIN-DAILY reconcile \
  --subscription-key acme-research-2026 \
  --run-key acme-2026-07-16-daily
```

Reconciliation compares the subscription balance projection, summed ledger deltas and business vouchers (`credit_grants`, active reservations, settlements and adjustments). A drift result exits unsuccessfully and must be investigated; this command never repairs balances.

## Generate a signed billing statement

`BILLING_STATEMENT_SIGNING_SECRET` must be independent from authentication and cursor keys. Statements only close completed periods. The export contains metering line items and identifiers, not MCP result payloads or source data.

```bash
pharma-commercial --tenant-slug acme --actor FIN-CLOSE-202607 generate-statement \
  --subscription-key acme-research-2026 \
  --statement-key acme-2026-07-r1 \
  --period-start 2026-07-01T00:00:00Z \
  --period-end 2026-08-01T00:00:00Z \
  --revision 1 \
  --output /approved-exports/acme-2026-07-r1.json
```

The command refuses to overwrite different content. `BillingProviderAdapter` is the versioned integration boundary. The normal path is the outbound-only `pharma-billing-provider` worker. It consumes `commercial.billing_statement_created.v1`, verifies the stored statement signature, resolves the server-owned `BillingAccount.external_customer_reference`, and sends `POST <BILLING_PROVIDER_BASE_URL>/v1/invoices` with a deterministic `Idempotency-Key`. Redirects, oversized or malformed responses, provider identity changes and payment-card metadata fail closed.

Enable the optional local Compose profile only after the provider settings are present:

```bash
docker compose --profile billing-provider up -d billing-provider
pharma-billing-provider --status
pharma-billing-provider --once
```

Transient network, `408`, `425`, `429` and provider `5xx` responses use a bounded exponential retry. Permanent protocol/accounting failures and exhausted attempts enter a durable dead-letter state and emit both an audit record and `commercial.billing_delivery_dead.v1`. After the cause is corrected, replay through the worker command instead of editing delivery rows:

```bash
pharma-billing-provider --retry-dead --tenant-id 00000000-0000-0000-0000-000000000000
```

Finance operators use the existing human Web workspace under `商业运营 -> 账单投递`; this is not a third public entry. The same operations are available under the authenticated human API:

- `GET /api/v1/commercial/billing-accounts` lists tenant accounts, mapping status and statement/invoice counts.
- `POST /api/v1/commercial/billing-accounts/{account_id}/provider-mapping` writes a server-owned provider customer reference and requires an audit reason. Responses expose only a masked value; audit and outbox records contain hashes, never the raw reference.
- `GET /api/v1/commercial/billing-deliveries` lists pending, processing, retry, succeeded and dead states with statement and invoice references.
- `POST /api/v1/commercial/billing-deliveries/{delivery_id}/replay` requeues only a dead delivery and requires an audit reason. Fix and verify the provider mapping or outage before replaying.
- `GET /api/v1/commercial/billing-disputes` lists tenant-scoped cases and exposes explicit owner, optimistic version, due time and overdue state.
- `POST /api/v1/commercial/billing-disputes` opens an idempotent case against an existing signed billing statement. Finance operators can start it directly from a statement row in the Web workspace.
- `POST /api/v1/commercial/billing-disputes/{dispute_id}/transition` accepts an idempotent operation key and expected version. Cases move from `open` to `investigating`, then to `resolved`, `rejected` or `cancelled`; terminal cases cannot be reopened.

`BILLING_DISPUTE_SLA_HOURS` controls the response window and defaults to 120 hours. A credit resolution requires an independent adjustment key and positive credit no greater than the disputed units. The case decision, immutable event, audit/outbox records, negative usage adjustment and ledger update commit in one database transaction. A failed balance or accounting check rolls back the decision. Dispute events are append-only under PostgreSQL, while the current case row uses optimistic versioning to reject stale browser decisions.

Billing disputes are a human finance workflow and are deliberately absent from MCP. Agent clients can obtain licensed pharmaceutical data through the paid MCP entry but cannot open, approve or alter financial cases.

All routes require a human principal and `commercial:read` or `commercial:write`. An initial mapping may repair statements that could not be delivered; rotating an existing mapping is blocked while statements remain without an invoice. Use the CLI bulk replay only for an approved incident recovery across multiple deliveries.

The provider response contains only `provider`, `external_invoice_id`, `status`, `amount_due`, `currency` and bounded scalar metadata. Metadata keys are restricted to `accounting_reference`, `credit_note_reference`, `delivery_reference`, `invoice_reference`, `payment_status_reference`, `provider_request_id` and `tax_reference`; payment-card data and arbitrary nested payloads fail closed. The resulting `InvoiceReference` remains append-only. A crash after provider acceptance or local invoice recording is safe because retries reuse the same provider idempotency key and an existing local invoice bypasses another external call.

The Kubernetes worker mounts a dedicated Secret containing only its dynamic database lease, tenant-context signing key, billing-statement signing key and provider token. It does not receive Web/OIDC, MCP, object-store or AI credentials. Its NetworkPolicy permits DNS, PostgreSQL, OTLP and provider HTTPS only. Validate migrations, runtime-role RLS, concurrent claiming and append-only accounting against a disposable local PostgreSQL database with:

```bash
make commercial-database-acceptance
```

The following manual command is an audited recovery path for an approved provider receipt, not the normal integration:

```bash
pharma-commercial --tenant-slug acme --actor FIN-CLOSE-202607 record-invoice \
  --statement-id 00000000-0000-0000-0000-000000000000 \
  --provider approved-erp \
  --external-invoice-id INV-2026-000421 \
  --status issued \
  --amount-due 12000.00 \
  --currency CNY
```

The repository provides the provider-neutral HTTPS protocol, durable worker and authoritative internal dispute/credit workflow, not a vendor account or tax/payment product. Provider-specific tax calculation, collection, external credit-note issuance and status synchronization remain customer integrations. Production still requires a real provider, customer mapping, dispute/credit-note synchronization, outage/retry/reversal/concurrency drills and Finance/Product approval under the `billing_provider` release gate.

## Incident behavior

- Missing client, subject, subscription, entitlement, or balance: fail before any domain data is read.
- Invalid, expired or query-mismatched pagination cursor: HTTP keeps its denied 403 status and adds `code: INVALID_CURSOR`; MCP exposes the same allowlisted code with a safe restart-query message. Do not treat this as a missing subscription or retry the invalid cursor. Arbitrary upstream details, oversized bodies and unknown codes are never forwarded.
- Domain execution failure: release the reservation and do not settle usage.
- Client cancellation can race with durable settlement. A completed settlement remains billable and is returned by replaying the same idempotency key; a cancellation observed before settlement must release its reservation. In either case, verify zero active reservations and reconcile charged, consumed and available units before closing the incident.
- Client transport timeout: retry with the same idempotency key until the bounded recovery window reaches `settled` or `released`; a settlement returns the original durable result without another charge, while a released key remains closed and a new logical attempt requires a new idempotency key.
- Settlement-response timeout after durable settlement: retry with the same idempotency key; the durable result and original settlement are returned.
- Abandoned reservation: run `expire-reservations`, then `reconcile`. Do not modify counters manually.
- Coverage or page-depth denial: inspect immutable `commercial_policy_events`, contract limits, client identity and cursor chain. Never rewrite coverage history.
- Ledger mismatch or immutable-history trigger failure: stop commercial traffic for the affected tenant, preserve evidence, and escalate as a financial P0.
