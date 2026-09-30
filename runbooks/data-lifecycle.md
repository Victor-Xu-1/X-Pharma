# Data lifecycle operations

This runbook governs retention deletion for commercial export artifacts and dependency-closed withdrawal of missing
source assets. The implementation is tenant-scoped, fail-closed, checksum-verified, idempotent, and auditable. It does
not claim that backups, downstream customer copies, or source assets with published dependencies have been legally
deleted.

## Current scope

- Data classes: `commercial_export_artifact` and `source_asset_snapshot`.
- Objects: export payloads and signed manifests; raw and extracted objects for eligible missing source assets.
- Human entry: Web workspace, **商业运营 -> 数据生命周期**.
- API namespace: `/api/v1/commercial/data-lifecycle/*`; it is an internal Web backend contract, not a third public
  product entry.
- Required identity: human workspace user with `commercial:read` or `commercial:write`.
- Database controls: forced tenant RLS and an append-only trigger on `data_lifecycle_events`.

Source withdrawal is permitted only for an asset already marked `missing`, after its approved retention period, and
only when dependency analysis finds no published staged fact, evidence claim, knowledge citation, or other domain-table
reference. A committed withdrawal immediately disappears from API search results and emits `source.asset.deleted` for
idempotent OpenSearch cleanup. Backups, customer exports, license obligations, and downstream copies remain outside
this operation and require their own approved procedures.

## Policy setup

1. Confirm the approved legal basis, geography, minimum contract retention, and backup obligations with Legal and the
   data owner.
2. Open **数据生命周期** and create separate export-artifact and source-asset retention policies as required.
3. Use at least 300 seconds. Production values must come from an approved schedule; the minimum exists only to make
   accidental immediate deletion impossible.
4. Verify the new policy version, operator identity, and audit event.
5. A missing or inactive policy blocks candidate discovery and deletion.

Policy changes are versioned in place. A purge event records the exact policy ID and version used for the decision.

## Legal hold

Supported scopes are:

| Scope | Scope ID |
|---|---|
| Entire tenant | none |
| Billing account | existing billing account UUID |
| Data export job | existing export job UUID |
| Data source | existing data source UUID |
| Source asset | existing source asset UUID |

Place the hold before investigating or changing retention. The service serializes hold placement, release, and purge on
the tenant row so a concurrent purge cannot pass an active hold check. A hold requires a matter reference and reason.

Release requires a separate reason. Released holds remain in the database. They are not deleted or reused.

## Purge procedure

1. Review the candidate's dataset, job ID, size, completion time, and expiration time.
2. Confirm that no legal hold should apply.
3. Submit a specific deletion reason.
4. The service verifies all of the following:
   - active tenant and active retention policy;
   - completed or expired job;
   - artifact TTL and policy retention period have both elapsed;
   - no tenant, billing-account, or job legal hold;
   - object URI belongs to the configured object store;
   - stored content checksum matches the authoritative database digest.
5. The service removes payload and manifest, clears live object references and signing material, marks the job expired,
   and appends a lifecycle event.

The idempotency key must be unique per intended action. Replaying the same key and target returns the original event.
Reusing it for another target is rejected.

New exports use job-specific object namespaces. For older content-addressed exports that share a physical object, the
service clears only the selected job reference and retains the object until the final database reference is released.

## Source withdrawal procedure

1. Confirm that the registered connector has authoritatively marked the asset `missing`; source outages are not
   withdrawal candidates.
2. Review file path, missing timestamp, object/version counts, and every dependency count in the Web impact preview.
3. Confirm there is no tenant, data-source, or source-asset legal hold.
4. Submit a specific withdrawal reason. The service rechecks policy eligibility and dependencies while holding the
   tenant and asset rows.
5. A blocked attempt appends an immutable event and leaves all objects and references unchanged.
6. A successful attempt checksum-deletes unshared raw and extracted objects, removes unpublished extraction/review
   residue, clears source-version live references, removes unshared source documents and retrieval projections, marks
   the asset `deleted`, and emits the search-withdrawal event.

Content-addressed objects and source documents referenced by another source version are retained. A connector scan will
not reactivate a `deleted` asset; it records a non-retryable governance finding until an operator completes the explicit
reauthorization procedure below.

## Source reauthorization procedure

1. Restore or renew the source license, contract, consent, or ownership basis outside the platform and record the
   approved change reference.
2. Confirm the registered data source is `active`, its source retention policy is active, and no tenant, data-source, or
   source-asset legal hold applies.
3. In **已撤回源资料**, select the exact logical path, review its withdrawal timestamp, and submit a specific reason.
4. The service serializes the operation on the tenant, data source, and source asset; an active hold records a blocked
   immutable event and leaves the tombstone unchanged.
5. Success changes only the asset from `deleted` to `missing`, clears its connector fingerprint, and emits an immutable
   reauthorization event. It does not restore raw objects, extracted text, documents, facts, citations, or search data.
6. The next scheduled connector scan snapshots and processes the current file as a new monotonically numbered
   `SourceVersion`, even when its digest matches a withdrawn historical version. Search remains withdrawn until that new
   version is parsed and projected.

Use a new idempotency key for reauthorization. Reusing a purge key for the same asset is rejected, while replaying the
same reauthorization key returns its original event.

## Failure recovery

- **No active policy**: configure or reactivate an approved policy; do not bypass the check in SQL.
- **Not eligible**: verify both `expires_at` and `completed_at + retention_seconds`.
- **Legal hold active**: stop. Release only after written legal authorization.
- **Checksum mismatch**: treat as a P1 integrity incident. Preserve the object and database record; investigate storage
  mutation or metadata corruption.
- **Partial external deletion**: retry with the same idempotency key only if no lifecycle event committed. Object deletion
  is idempotent, so an already absent object can be reconciled while the remaining object and database state complete.
- **Shared legacy reference**: expected outcome is `retained_shared_reference`; purge the other eligible jobs before the
  final physical deletion.
- **Published or domain dependency**: do not delete references in SQL. Withdraw or supersede the governed business
  record through its owning domain workflow, then perform a new impact review.
- **Search cleanup delayed**: API delivery filters deleted asset IDs immediately. Drain or replay the OpenSearch
  projector and verify that `source.asset.deleted` reaches `succeeded`.
- **Source file returns**: automatic ingestion remains fail-closed until the controlled reauthorization procedure is
  complete. Do not change `source_assets.state` directly in SQL.

Never manually clear URIs, signatures, hashes, holds, or lifecycle events.

## S3 production requirements

Before Production approval, the target bucket must provide versioning, encryption with the approved KMS key, access
logging, lifecycle policy reconciliation, least-privilege delete credentials, and tested object restore. Where regulatory
or contractual retention requires WORM, configure S3 Object Lock and prove that application deletion cannot bypass it.
Object-store lifecycle rules must not delete data earlier than the platform policy.

## Verification

```bash
.venv/bin/pytest -q tests/test_object_store.py tests/test_data_lifecycle.py tests/test_data_lifecycle_api.py tests/test_data_factory.py tests/test_search_projection.py
PATH="$HOME/.local/bin:$PATH" bash scripts/verify-commercial-postgres.sh
cd apps/web
pnpm exec vitest run src/test/CommercialView.test.tsx
```

The PostgreSQL check creates a disposable database, migrates from the first revision to head, provisions the non-owner
runtime role, performs real export and source-object purges, verifies forced RLS, and proves lifecycle events reject
mutation.

## Production evidence

Production evidence must still include Legal and data-owner approval for the contract inventory, field/channel rights,
retention and deletion schedule, geography, backup behavior, source withdrawal, downstream copies, and legal hold
procedure. This local implementation is supporting technical evidence, not that approval itself.
