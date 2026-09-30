# ADR 0005: MCP commercial metering and anti-extraction controls

- Status: Accepted target architecture
- Date: 2026-07-16
- Scope: Production MCP identity, entitlements, metering, settlement, quotas, export control and abuse response
- Depends on: ADR 0001, ADR 0003 and ADR 0004

## Context

The MCP endpoint exposes valuable licensed pharmaceutical data to automated clients. Authentication and per-request rate limiting are necessary but insufficient. A paid client can still enumerate a dataset slowly, spread reads across credentials, retry calls that are charged twice, or use an interactive query endpoint as an unapproved bulk export channel.

The platform must monetize successful MCP data delivery while preserving predictable costs for Agent clients, financial auditability, source-license restrictions and normal research workflows. Billing failures must not silently turn a commercial endpoint into free access. Security controls must not corrupt scientific facts or claim that copying data already delivered to a client is technically impossible.

## Decision

### Commercial identity and entitlement

Every production MCP call is bound server-side to an OAuth subject, preregistered client, tenant, customer billing account and active subscription. Callers cannot submit or override billing identities. Uncontrolled dynamic client registration and shared production credentials are disabled by default.

Authorization requires all of the following:

1. MCP connection and domain scopes.
2. Tenant and entity/field/source authorization.
3. Source-license and export policy.
4. Product-plan entitlement.
5. Available per-call, periodic and monetary budget.
6. Abuse-risk policy approval.

Payment never overrides data authorization or source-license restrictions.

### Authoritative ledger

The application owns an append-only PostgreSQL commercial ledger in a dedicated domain schema. The minimum records are:

- `BillingAccount`, `Subscription` and immutable `RateCardVersion`.
- `Entitlement` and `CreditGrant`.
- `UsageReservation`, `UsageEvent` and `UsageSettlement`.
- `Adjustment`, `Reversal` and `InvoiceReference`.

Reservations and settlements use the same PostgreSQL transaction boundaries and transactional outbox pattern as other authoritative application state. Corrections append balancing records; they never update or delete settled history. Valkey may accelerate rate and balance checks but is not a financial authority.

Billable result counts and amounts are exact ledger values. HyperLogLog or other approximate-cardinality structures may provide early abuse signals in Valkey or ClickHouse, but they cannot calculate invoices. A punitive action based on approximate coverage requires an exact event check, an approved conservative threshold or human review.

### Billable units

Every successfully delivered production MCP call is metered. A versioned rate card can combine:

- invocation units by tool billing class;
- result units by delivered records, claims, evidence fragments or bytes;
- compute units for chemistry, semantic ranking or costly external sources;
- export units for approved asynchronous packages.

The rate card, unit rounding rules, included allowance, overage, currency and effective period are immutable for a settlement. Charging solely by HTTP request count is rejected because tools have materially different output and compute costs.

Initialization, capability discovery, entitlement/quote reads and asynchronous status polling deliver no commercial dataset and use an auditable zero-rated billing class by default. They remain rate-limited and abuse-monitored. A domain data call cannot be disguised as a control-plane call.

Every billable tool accepts a client idempotency key and maximum billable-unit guard. The service calculates a worst-case quote from the requested bounds, atomically reserves credit before reading commercial data, settles actual successful delivery and releases the remainder. Retries with the same idempotency key return the existing outcome and cannot create a second charge.

Reservations have explicit `reserved`, `settled`, `released` and `expired` states, a bounded lease and a reconciler. Long asynchronous jobs renew or split reservations before expiry. The reconciler releases an abandoned reservation only after proving that no durable result or settlement exists. Balance mutation uses transactional locking or compare-and-swap so concurrent requests cannot overspend one allowance.

A synchronous result and its settlement are persisted before the response is sent. If the connection drops after persistence, retrying the idempotency key returns that durable result and settlement without charging again. A failure before a durable result exists releases the reservation and creates no financial settlement. The platform does not claim network-level exactly-once delivery.

Authentication failures, authorization failures, quota/risk denials and platform 5xx failures are not financially settled, but they remain security-rate events. The current governed export contract reserves after any required approval and settles the completed immutable artifact once using actual record and byte counts. Cancellation or failure before completion releases the reservation and creates no settlement; a future partial-delivery product would require a new rate-card and chunk-settlement contract.

### Request lifecycle

The required order is:

1. Authenticate and bind commercial identity.
2. Authorize domain, field, source and export access.
3. Check subscription entitlement and abuse policy.
4. Estimate and reserve the caller-approved maximum units.
5. Execute a bounded domain use case.
6. Settle actual delivery and release unused reservation.
7. Commit usage/outbox records and return settlement metadata.
8. Aggregate, invoice and reconcile asynchronously.

Production fails closed when entitlement, reservation or authoritative settlement is unavailable. A contractual grace mode is allowed only when explicitly configured with a hard cap, durable deferred-settlement events, alerts and reconciliation.

### Anti-extraction controls

Protection is layered:

- Envoy Gateway applies local burst, global distributed and bandwidth limits.
- The application applies customer, tenant, subject, client, tool, data-domain, source-license and time-window limits.
- Interactive tools enforce maximum fields, date range, query complexity, evidence length, response bytes, concurrency, page depth and cumulative unique entity/claim coverage.
- Pagination uses short-lived opaque signed cursors bound to subject, tenant, client, tool, normalized query hash, page size and expiry. Arbitrary offset and internal-ID scans are not exposed.
- Raw files, full text and large results require a separate export scope, entitlement, asynchronous job, encrypted expiring delivery and signed manifest.
- Risk evaluation correlates sequential-ID scans, alphabet/numeric partitioning, deep pagination, low-selectivity polling, rapidly expanding windows, unusual unique-record coverage, credential/network rotation and coordinated clients.
- Responses to abuse are explicit throttling, cooldown, denial, step-up authentication, review, subscription suspension or client revocation. The platform never inserts false records or silently changes scientific values.

Paying for overage does not grant unlimited enumeration. Per-call rate limits and cumulative data-coverage limits are independent controls.

### Usage event projection and OpenMeter

The ledger emits idempotent CloudEvents with stable event IDs. Core Commercial Production can aggregate these events with platform-owned outbox consumers.

OpenMeter is the selected Scale Production metering/subscription projection only after a stable v1 GA or later release passes production qualification. At this decision date, the official repository is still on a v1.0.0 beta release line. It must not be the authoritative balance or settlement store and must not be required for a Core Commercial MCP call.

OpenMeter may consume the platform events for high-volume aggregation, entitlements, subscription views and invoice adapters. PostgreSQL settlements remain the reconciliation source. Invoice/payment/ERP providers are connected through a replaceable adapter; payment-card data does not enter the platform.

### Client-visible contract

Every successful fact response includes a standard commercial-control object containing:

- `usage_record_id` and settlement status;
- `rate_card_version` and billing class;
- `units_reserved`, `units_charged` and `quota_remaining`;
- currency/amount when the customer contract permits disclosure;
- applied result, pagination, export and policy limits;
- `policy_limited` and a stable reason code when scope was reduced or denied.

The human workbench shows authorized customers usage, remaining allowance, export history, invoice references and disputes. Operations views aggregate cross-client risk under separate least-privilege roles.

## Alternatives rejected

- **Gateway request counting only**: cannot price different tool costs, reconcile delivered records or detect slow enumeration.
- **Valkey as the balance authority**: expiration, eviction and failover behavior are unsuitable for the financial system of record.
- **OpenMeter as the immediate critical-path authority**: its current pre-GA release and Kafka/ClickHouse topology add avoidable commercial-core risk.
- **Unlimited access for paying customers**: conflicts with source licensing and makes credential abuse commercially acceptable.
- **Hidden truncation or synthetic canary facts**: damages scientific integrity and makes responses non-reproducible.
- **Per-IP blocking only**: automated enterprise clients share egress IPs and abusive clients can rotate networks.

## Consequences

- MCP billing becomes a domain capability, not an API-gateway plugin.
- The commercial ledger requires migrations, concurrency controls, reconciliation and financial-grade tests.
- Normal Agent calls gain explicit cost guards and machine-readable quota state.
- Bulk export is a separate licensed product capability rather than a larger page size.
- Anti-extraction analytics must account for privacy, retention and false-positive review.
- OpenMeter can be adopted later without changing MCP tool semantics or authoritative settlements.

## Production gates

The PostgreSQL ledger, settlement/reconciliation, signed cursors, exact coverage records, billing-account risk policy and governed asynchronous export are implemented. The account policy serializes concurrent subscriptions and enforces account daily coverage, request-window, distinct-client, privacy-preserving network, credential-confirmation, partition and cross-client partition limits with hashed signals and immutable policy events. Export adds an account-locked policy, `data:export` scope, separate entitlement/rate class, approval threshold, Temporal execution, immutable object/checksum, independent HMAC manifest, owner-bound chunk cursor, expiry, cancellation compensation and actual record/byte settlement. A provider-neutral HTTPS billing adapter and durable outbox consumer now enforce signed statements, server-owned customer mapping, deterministic idempotency, strict receipt schemas, bounded retries, dead-letter audit and explicit replay. Its Kubernetes role has a dedicated dynamic database/signing/provider Secret and restricted egress. Real PostgreSQL tests run through the `NOBYPASSRLS` runtime role and prove concurrent billing claims, one invoice reference, cross-tenant invisibility, concurrent cross-client denial and concurrent account export allocation; a real local Temporal workflow proves one artifact maps to one settlement. Target proxy CIDR/DPoP or mTLS enforcement, external alerts, gateway load and a customer-selected billing provider remain open production gates.

Production remains blocked until real tests prove:

- concurrent reservation cannot overspend a balance;
- idempotent retries and replay cannot double-charge;
- failed and denied calls follow the published charging policy;
- ledger, aggregation and invoice totals reconcile;
- signed cursors cannot be reused across subjects, clients, queries or expiry;
- normal target/competitor research completes within plan limits;
- partitioned enumeration, deep pagination, coordinated clients and export bypass attempts are detected and controlled;
- billing or risk-service outages follow the approved fail-closed/grace policy;
- abandoned reservation recovery and connection-loss retries cannot lose credit, lose a settled result or double-charge;
- customer usage statements and dispute adjustments are reproducible from immutable records.
