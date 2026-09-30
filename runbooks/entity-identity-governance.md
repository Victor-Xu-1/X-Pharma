# Entity identity and ontology governance

This runbook covers governed identifier normalization, ontology registration and reversible entity resolution. PostgreSQL is authoritative; do not repair identity by editing OpenSearch or generated Markdown.

## Access

- `governance:read` lists namespaces, ontology terms and resolution cases.
- `governance:review` plus a human user identity registers terms, creates mappings and decides cases.
- Service API keys and MCP principals cannot make review decisions.

Use the Web workspace Governance view for routine case review. The internal API remains an implementation interface and must not become a third public product entry.

## Review procedure

1. Filter pending cases and review high-risk cases first.
2. Compare trusted namespace identifiers, source provenance, entity type and the machine-generated reason list.
3. Approve only when both rows represent the same real-world object. Approval creates a canonical link; it does not delete either row.
4. Reject when identifiers conflict or evidence is insufficient. Record a reason for rejection.
5. Revert an approved case when later evidence disproves the link. The decision trail remains append-only.

Never resolve solely from normalized display name, embedding similarity or an LLM assertion. Do not approve cross-type mappings or chains that would create a canonical-link cycle.

## Ontology lifecycle

Register a new ontology release under its exact upstream version. Reusing a version with changed term content is rejected by design. Map only terms whose entity type matches the entity. Preserve `source_uri`, evidence and source document references where available.

Before deprecating an ontology version:

1. Register and validate the replacement version.
2. Create reviewed replacement mappings.
3. Rebuild affected search and knowledge projections.
4. Retain the old version for historical reproducibility; mark it inactive only after consumers have moved.

## Verification

Run the consolidated backend, frontend, database and dual-entry gates:

```bash
EVIDENCE_ROOT="${PHARMA_RUNTIME_EVIDENCE:-manifests/runtime/manual/entity-identity}"
mkdir -p "$EVIDENCE_ROOT"
make container-backend-check
make container-frontend-check
make database-acceptance DATABASE_EVIDENCE="$EVIDENCE_ROOT/database.json"
make entry-consistency-acceptance \
  ENTRY_CONSISTENCY_EVIDENCE="$EVIDENCE_ROOT/entry.json"
./scripts/run-browser-acceptance.sh \
  --output "$EVIDENCE_ROOT/browser.json"
```

`TEST_MCP_ACCESS_TOKEN` must be supplied from a deployment-specific secret path outside Git before running entry consistency. A passing gate must leave no temporary user, entity, identifier, resolution or OpenSearch fixture.

## Incident handling

For a suspected incorrect merge, stop projection rebuilds that depend on the affected canonical ID, revert the resolution case, record the incident reference in review notes, and rebuild entity/evidence/knowledge projections. Do not delete decision rows. For broad corruption, restore PostgreSQL to an isolated environment first and compare append-only decisions before changing production.
