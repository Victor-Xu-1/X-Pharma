# SLO and error-budget operations

The machine authority for service ownership, indicators, targets and alerts is `deploy/operations/operations-contract.yaml`. The contract is provider-neutral; the target observability backend must implement equivalent queries and paging routes during pre-production onboarding.

## Evaluation

- Availability and settlement ratios use durable outcomes, not client-side success messages.
- Latency histograms use server-side end-to-end durations and exclude no successful request from the denominator through sampling.
- Server metric labels are restricted to service, operation, consumer, outcome and bounded billing class. Browser Web Vitals additionally allow only workspace route, device class, navigation type, metric name and rating. Tenant IDs, user IDs, entity/document IDs, URLs, query text, network addresses and credentials are prohibited.
- Fast-burn alerts page the owning team. Slow-burn and latency alerts create an owned work item. Missing telemetry is an alert condition, not a healthy value.
- Scheduled maintenance only leaves an SLO denominator when approved before the event and represented consistently in the central backend.

## Error-budget policy

1. At 50% budget consumption, the service owner reviews capacity, dependency failures and recent changes.
2. At 75%, pause noncritical changes to the affected service and require an explicit reliability review.
3. At 100%, freeze non-remediation changes. MCP settlement or tenant-isolation violations always trigger P0 handling regardless of remaining budget.
4. Restoring the metric below threshold does not automatically unfreeze changes; the owner records cause, recovery evidence and approval.

## Alert onboarding

1. Run `pharma-operations-verify` and bind the resulting report to the exact candidate commit.
2. Translate every objective and alert into the target backend without renaming the semantic metric or dropping filters.
3. Route warning and critical notifications to the role-backed escalation policies. Exercise acknowledgement, escalation and notification failure.
4. Inject one controlled failure per component and retain the alert, trace, log, runbook execution and recovery evidence.
5. Platform and operations approvers compare the deployed rules against the contract before signing `operations_approval` and `performance` evidence.

## Dashboard minimum

Each entry/service dashboard shows request or operation volume, success/failure ratio, P50/P95/P99, saturation/backlog, active reservations, projection retries/dead letters and deployment version. The external workspace dashboard also shows sample volume and LCP/INP/CLS/TTFB P75 by bounded route, device and navigation type without identity dimensions. Billing views additionally show signed statements, pending/retry/dead deliveries and reconciliation difference. Dashboards must link to the corresponding runbook and deployment change.
