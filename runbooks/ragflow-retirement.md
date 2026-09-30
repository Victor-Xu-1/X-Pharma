# RAGFlow retirement and offline export

RAGFlow is not an online dependency of the API, ingestion worker, Temporal workflow, Web workspace or MCP service. New evidence is parsed into immutable object storage, committed to PostgreSQL and projected to OpenSearch through the transactional outbox.

The database still contains nullable legacy RAGFlow ID columns so an upgrade does not destroy an operator's last migration map. Core runtime code does not read or write those columns. Removing them requires a separately approved destructive migration after every customer confirms export completion.

## Offline export

Use the isolated read-only exporter from an operator workstation. It accepts only HTTPS endpoints, except loopback for a local migration appliance; credentials come from a named environment variable and are never written to the export. Private dataset IDs are replaced by logical keys and represented only by SHA-256 in the manifest.

```bash
export RAGFLOW_MIGRATION_API_KEY='replace-at-runtime'
printf '["EGFR", "KRAS G12D"]\n' > /secure/migration-queries.json
pharma-ragflow-migration-export \
  --base-url https://legacy-ragflow.example \
  --dataset literature=private-dataset-id \
  --query-file /secure/migration-queries.json \
  --limit 100 \
  --output /secure/ragflow-export.json
```

The exporter is bounded to 100 queries, 100 chunks per query, 32 MiB per provider response and 256 MiB per export. It rejects redirects, unapproved returned dataset IDs, malformed responses, missing credentials and output overwrite. The export is a migration review artifact, not authoritative platform data. After licensing review, material selected for retention must enter through a registered read-only source and the normal snapshot, malware, parser, governance and publication chain.

## Exit check

Before approving the destructive legacy-column migration:

1. Record every legacy tenant and dataset mapping outside the production application database.
2. Compare approved export counts and source identifiers with the legacy system.
3. Ingest approved source packages through the normal Data Factory and verify Web/MCP citations against immutable source versions.
4. Rebuild OpenSearch and verify representative evidence queries without RAGFlow connectivity.
5. Disable legacy credentials and retain the signed export under the customer's retention policy.
