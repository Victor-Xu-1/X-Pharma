# Incident response and escalation

This runbook defines the platform response boundary. Customer-specific people, paging destinations and ticket queues are bound to the role references in `deploy/operations/operations-contract.yaml` during pre-production approval; they are not committed as personal contact data.

## Severity

| Severity | Examples | Initial response | Authority |
|---|---|---:|---|
| P0 | Cross-tenant disclosure, successful commercial result without settlement, ledger corruption, active credential compromise | 5 minutes | incident command + security + business owner |
| P1 | Both public entries unavailable, billing close blocked, irreversible source corruption risk, sustained SLO fast burn | 15 minutes | incident command + owning operation team |
| P2 | One source unavailable, projection backlog with canonical reads healthy, degraded noncritical workflow | 60 minutes | owning operation team |
| P3 | Cosmetic defect, documentation issue, non-urgent capacity trend | next business day | service owner |

Acknowledgement means a named operator has accepted command and opened an immutable incident record. It does not mean the alert was merely delivered.

## First actions

1. Assign incident command, operations lead, communications lead and scribe. Record environment, start time, candidate commit/image digest and alert identity.
2. Preserve logs, traces, metrics, audit events, outbox state, usage ledger and deployment events. Never paste tokens, full queries, source content or customer data into the incident record.
3. Bound impact by tenant, public entry, source, projection and billing period. Do not use unrestricted production database queries from an Agent.
4. For suspected cross-tenant access or commercial delivery without settlement, stop the affected public path before investigation. Preserve canonical data and append-only ledgers.
5. For ingestion or projection failures, pause only the affected source/consumer when isolation is proven. Do not delete snapshots, rewrite cursors, clear exact coverage or edit delivery attempts.
6. Choose rollback only when schema compatibility, migration direction and evidence retention are verified. Otherwise roll forward under change control.

## Component containment

| Signal | Containment | Recovery proof |
|---|---|---|
| MCP settlement failure | Disable affected client/account or MCP route; expire abandoned reservations through the supported command | one result to one settlement, zero active leaked reservations, reconciliation difference zero |
| Billing delivery dead letter | Stop billing close for the account; repair mapping/provider; use audited replay | one provider invoice reference, idempotency key unchanged, signed statement reconciled |
| OpenSearch dead letter | Keep canonical reads available; stop alias cutover; repair and explicitly replay | dead/retry zero, canonical/projection count match, representative citations pass |
| Source or parser failure | Pause affected source; retain immutable snapshot and finding | source cursor unchanged on failure, clean sample passes scanner/parser, failed versions remain auditable |
| Credential compromise | Revoke at IdP/OpenBao, rotate independent secret, roll affected workloads | old credential rejected, new lease active, no unauthorized audit events |
| Suspected tenant leak | Stop both affected entry paths and preserve all evidence | independent security review, RLS/authorization reproduction, customer/legal approval before reopen |

## Closure

P0/P1 incidents require a timeline, customer impact, root cause, control failure, corrective actions with owners/dates, evidence retention reference and approval from operations and the affected business/security owner. A passing smoke test alone cannot close an incident. Recurring corrective actions must enter the normal change and release evidence process.
