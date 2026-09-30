# Monitoring operations

The monitoring worker consumes canonical entity, governed fact publication and compiled knowledge
events under the durable `monitoring-v1` consumer identity. It evaluates versioned structured saved
searches that existed when the source event occurred and appends immutable alerts. Read receipts are
stored separately so alert evidence remains unchanged; old outbox history does not create alerts for
new topics.

## Triage

1. Confirm the unified `worker`/`pharma-jobs` process is healthy, `pharma-jobs-health` passes, and `MONITORING_ENABLED=true`.
2. Inspect `projection_deliveries` for `consumer_name='monitoring-v1'`, grouped by `state`.
3. Correlate a failed delivery through `outbox_event_id`; do not mutate or delete the source event.
4. Correct the underlying schema, database, or query-contract failure before replay.

## Replay

Run `pharma-monitoring retry-dead --tenant-id <tenant-uuid>` from an approved operator context.
Inspect progress with `pharma-monitoring status`. Replay is idempotent:
`monitoring_alerts` is unique on tenant, topic, and source event. Every dead-letter replay is audited.

## Customer impact

Search and MCP retrieval continue to operate when monitoring is impaired. Inform affected tenants
that change notifications are delayed; do not describe delayed alerts as lost until replay has failed.
