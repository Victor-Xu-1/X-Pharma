# ADR 0007: Durable saved-search monitoring

## Status

Accepted.

## Context

The human workbench requires saved searches, enterprise sharing, monitoring topics and change alerts. Browser-only saved state cannot survive devices, cannot enforce tenant visibility and cannot prove which canonical change produced an alert. Running alert logic inside request handlers would lose changes during outages and couple user latency to notification work.

## Decision

- Store saved searches as structured `entity_search` contracts with immutable version history. Arbitrary SQL and executable expressions are rejected.
- Support private owner visibility and tenant-wide shared visibility. A user creates monitoring topics only for searches visible to that user.
- Emit canonical entity changes through the existing transactional outbox. A dedicated `monitoring-v1` consumer uses leases, bounded exponential retry, dead letters, audit and explicit replay.
- Append one alert per tenant, topic and source event. PostgreSQL rejects alert update and delete operations. Read status is stored in a separate receipt table.
- Operate the worker as an internal process with no public port. Web remains the only human entrance and MCP remains the only Agent entrance.
- Use a dedicated dynamic database Secret and tenant-context signing key in Kubernetes. The worker receives no Web session, MCP, model, object-store, search or billing credentials.

## Consequences

Alert generation is recoverable and idempotent, and search projection failures do not block monitoring. Query contracts must be explicitly versioned when new filter families are added. Delivery channels such as email or Teams are downstream adapters and may not become an alternate product entrance or mutate the authoritative alert event.
