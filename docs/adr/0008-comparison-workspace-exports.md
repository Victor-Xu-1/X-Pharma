# ADR 0008: Versioned comparison sets and governed human exports

- Status: Accepted
- Date: 2026-07-18

## Context

The human workspace needs the list and comparison workflow expected from a commercial pharmaceutical intelligence product. Analysts must collect stable entities, compare canonical fields, share selected lists inside a tenant and create ordinary spreadsheet or machine-readable extracts. The platform already has a commercial Agent export subsystem with entitlements, approval, Temporal execution, short-lived artifacts, billing and anti-extraction controls. Reusing that subsystem for every 5-20 row human spreadsheet would make the workspace awkward; bypassing it with an unrestricted download endpoint would create a data-exfiltration path.

## Decision

1. Human comparison sets are PostgreSQL authority objects. A set is private or tenant-visible, owner-editable, versioned with optimistic concurrency and limited to 20 stable entity IDs.
2. Every mutation appends an immutable snapshot containing metadata and ordered member IDs. PostgreSQL RLS isolates all current and historical rows by tenant.
3. Human standard exports are synchronous and limited to one comparison set. A tenant administrator must explicitly configure an export policy before any export is possible. The policy controls enabled state, formats, fields, attribution and record limit.
4. CSV, JSON and XLSX artifacts are generated from a canonical entity snapshot. Stable ID, entity type and name are mandatory. XLSX values are written as strings where appropriate so spreadsheet formulas from untrusted source values cannot execute.
5. Each export command has a user-scoped idempotency key and request hash. The server stores the bounded records snapshot, policy hash, artifact hash and byte count in an append-only event and must reproduce identical bytes before replaying it.
6. Comparison and human export APIs accept human sessions only. API keys and Agent principals cannot call them, even if a scope is mistakenly granted.
7. Agent bulk exports remain on the existing commercial path with entitlement, quota, approval, metering, billing and anti-enumeration controls. This decision does not add another product entrance: the public entrances remain the Web workspace and MCP.

## Consequences

- Analysts get a predictable comparison and standard-export workflow without weakening Agent commercial controls.
- Export policy changes require a new policy version when rights change; immutable events retain the exact policy and content evidence used at generation time.
- Human exports are intentionally unsuitable for bulk extraction. Larger or automated delivery must use the commercial Agent export contract.
- PostgreSQL migration tests must cover RLS, history immutability, concurrent mutation and upgrade/downgrade. Browser tests must cover the workspace interaction and download request contract.
