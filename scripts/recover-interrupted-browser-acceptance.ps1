[CmdletBinding()]
param(
  [Parameter(Mandatory)]
  [ValidatePattern('^[0-9a-f]{64}$')]
  [string]$BackupSha256,

  [Parameter(Mandatory)]
  [string]$BackupDirectory,

  [switch]$Apply,

  [string]$Confirmation = ''
)

$ErrorActionPreference = 'Stop'
$confirmationPhrase = 'CLEAN_SYNTHETIC_RUNTIME_DATA'

if (-not $Apply -or $Confirmation -ne $confirmationPhrase) {
  throw "Recovery requires -Apply -Confirmation $confirmationPhrase."
}

$backupPath = (Resolve-Path -LiteralPath $BackupDirectory).Path
$checksumsPath = Join-Path $backupPath 'checksums.sha256'
if (-not (Test-Path -LiteralPath $checksumsPath -PathType Leaf)) {
  throw "Verified backup checksums are required: $checksumsPath"
}

$expectedChecksums = @{}
foreach ($line in Get-Content -LiteralPath $checksumsPath) {
  if ($line -notmatch '^([0-9a-f]{64})\s+\*?(.+)$') {
    throw "Invalid backup checksum entry: $line"
  }
  $expectedChecksums[$Matches[2]] = $Matches[1]
}
foreach ($artifact in $expectedChecksums.Keys) {
  $artifactPath = Join-Path $backupPath $artifact
  if (-not (Test-Path -LiteralPath $artifactPath -PathType Leaf)) {
    throw "Backup artifact is missing: $artifact"
  }
  $actual = (Get-FileHash -LiteralPath $artifactPath -Algorithm SHA256).Hash.ToLowerInvariant()
  if ($actual -ne $expectedChecksums[$artifact]) {
    throw "Backup checksum mismatch: $artifact"
  }
}
if ($expectedChecksums['postgres.dump'] -ne $BackupSha256) {
  throw 'BackupSha256 must match the verified postgres.dump checksum.'
}

$docker = $env:PHARMA_DOCKER_EXE
if ([string]::IsNullOrWhiteSpace($docker)) {
  $docker = 'C:\Program Files\Docker\Docker\resources\bin\docker.exe'
}
if (-not (Test-Path -LiteralPath $docker -PathType Leaf)) {
  throw "Docker CLI was not found: $docker"
}

$composeItem = Get-Item -LiteralPath (Join-Path $PSScriptRoot '..\compose.yaml')
$compose = $composeItem.FullName
$previousContext = $env:DOCKER_CONTEXT
$env:DOCKER_CONTEXT = 'desktop-linux'
try {
  & $docker info | Out-Null
  if ($LASTEXITCODE -ne 0) {
    throw 'Docker Desktop is not ready.'
  }

  $postgresUser = (& $docker compose -f $compose exec -T postgres printenv POSTGRES_USER).Trim()
  $postgresDatabase = (& $docker compose -f $compose exec -T postgres printenv POSTGRES_DB).Trim()
  if ($postgresUser -notmatch '^[a-z_][a-z0-9_]*$' -or $postgresDatabase -notmatch '^[a-z_][a-z0-9_]*$') {
    throw 'PostgreSQL runtime returned an unsafe identity.'
  }

  function Invoke-RecoverySql([string]$Sql) {
    $Sql | & $docker compose -f $compose exec -T postgres psql -X -U $postgresUser -d $postgresDatabase -v ON_ERROR_STOP=1
    if ($LASTEXITCODE -ne 0) {
      throw 'Browser fixture recovery SQL failed.'
    }
  }

  $tenantId = (& $docker compose -f $compose exec -T postgres psql -X -U $postgresUser -d $postgresDatabase -At -v ON_ERROR_STOP=1 -c "SELECT id FROM tenants WHERE slug = 'default'").Trim()
  if ($tenantId -notmatch '^[0-9a-f-]{36}$') {
    throw 'The default tenant is required for browser fixture recovery.'
  }

  $fixtureIds = @(& $docker compose -f $compose exec -T postgres psql -X -U $postgresUser -d $postgresDatabase -At -v ON_ERROR_STOP=1 -c "SELECT id FROM entities WHERE tenant_id = '$tenantId' AND attributes ->> 'acceptance_fixture' = 'true' ORDER BY id") |
    Where-Object { $_ -match '^[0-9a-f-]{36}$' }
  $beforeAccounts = ((& $docker compose -f $compose exec -T postgres psql -X -U $postgresUser -d $postgresDatabase -At -v ON_ERROR_STOP=1 -c "SELECT count(*) FROM users WHERE tenant_id = '$tenantId' AND normalized_email LIKE 'e2e-%@example.test'").Trim())
  $beforeFixtures = $fixtureIds.Count

  $fixtureCleanup = @"
BEGIN;
CREATE TEMP TABLE browser_quality_issues (id varchar(36) PRIMARY KEY, snapshot_id varchar(36)) ON COMMIT DROP;
INSERT INTO browser_quality_issues
SELECT id, last_snapshot_id FROM data_quality_issues
WHERE tenant_id = '$tenantId' AND active_key LIKE 'browser:e2e-%';
DELETE FROM audit_events
WHERE tenant_id = '$tenantId' AND resource_type = 'data_quality_issue'
  AND resource_id IN (SELECT id FROM browser_quality_issues);
ALTER TABLE data_quality_issue_events DISABLE TRIGGER immutable_data_quality_issue_events;
DELETE FROM data_quality_issue_events
WHERE tenant_id = '$tenantId' AND issue_id IN (SELECT id FROM browser_quality_issues);
ALTER TABLE data_quality_issue_events ENABLE TRIGGER immutable_data_quality_issue_events;
DELETE FROM data_quality_issues
WHERE tenant_id = '$tenantId' AND id IN (SELECT id FROM browser_quality_issues);
DELETE FROM data_quality_snapshots
WHERE tenant_id = '$tenantId' AND id IN (SELECT snapshot_id FROM browser_quality_issues)
  AND definitions_version LIKE 'browser-e2e-%';

CREATE TEMP TABLE browser_publication_facts (id varchar(36) PRIMARY KEY, resource_id varchar(36)) ON COMMIT DROP;
INSERT INTO browser_publication_facts
SELECT id, published_resource_id FROM staged_facts
WHERE tenant_id = '$tenantId' AND fact_key LIKE 'browser-publication-e2e-%';
CREATE TEMP TABLE browser_publication_batches (id varchar(36) PRIMARY KEY) ON COMMIT DROP;
INSERT INTO browser_publication_batches
SELECT DISTINCT publication_batch_id FROM governance_publication_batch_items
WHERE tenant_id = '$tenantId' AND staged_fact_id IN (SELECT id FROM browser_publication_facts);
DELETE FROM projection_deliveries WHERE outbox_event_id IN (
  SELECT id FROM outbox_events WHERE tenant_id = '$tenantId'
    AND payload ->> 'staged_fact_id' IN (SELECT id FROM browser_publication_facts)
);
DELETE FROM outbox_events WHERE tenant_id = '$tenantId'
  AND payload ->> 'staged_fact_id' IN (SELECT id FROM browser_publication_facts);
DELETE FROM audit_events WHERE tenant_id = '$tenantId' AND resource_type = 'governance_publication_batch'
  AND resource_id IN (SELECT id FROM browser_publication_batches);
ALTER TABLE fact_withdrawal_tombstones DISABLE TRIGGER immutable_fact_withdrawal_tombstones;
DELETE FROM fact_withdrawal_tombstones
WHERE tenant_id = '$tenantId' AND staged_fact_id IN (SELECT id FROM browser_publication_facts);
ALTER TABLE fact_withdrawal_tombstones ENABLE TRIGGER immutable_fact_withdrawal_tombstones;
DELETE FROM governance_publication_batch_items
WHERE tenant_id = '$tenantId' AND staged_fact_id IN (SELECT id FROM browser_publication_facts);
DELETE FROM governance_publication_batches
WHERE tenant_id = '$tenantId' AND id IN (SELECT id FROM browser_publication_batches);
DELETE FROM fact_provenance_links
WHERE tenant_id = '$tenantId' AND staged_fact_id IN (SELECT id FROM browser_publication_facts);
DELETE FROM evidence_claims WHERE tenant_id = '$tenantId' AND id IN (
  SELECT resource_id FROM browser_publication_facts WHERE resource_id IS NOT NULL
);
DELETE FROM review_tasks WHERE tenant_id = '$tenantId' AND staged_fact_id IN (SELECT id FROM browser_publication_facts);
DELETE FROM staged_facts WHERE tenant_id = '$tenantId' AND id IN (SELECT id FROM browser_publication_facts);
DELETE FROM extraction_runs WHERE tenant_id = '$tenantId' AND model_provider = 'browser-acceptance';

DELETE FROM audit_events WHERE tenant_id = '$tenantId' AND resource_type = 'ingestion_run' AND resource_id IN (
  SELECT id FROM ingestion_runs WHERE tenant_id = '$tenantId' AND data_source_id IN (
    SELECT id FROM data_sources WHERE tenant_id = '$tenantId' AND name LIKE 'Browser replay e2e-%'
  )
);
DELETE FROM ingestion_run_operations WHERE tenant_id = '$tenantId' AND ingestion_run_id IN (
  SELECT id FROM ingestion_runs WHERE tenant_id = '$tenantId' AND data_source_id IN (
    SELECT id FROM data_sources WHERE tenant_id = '$tenantId' AND name LIKE 'Browser replay e2e-%'
  )
);
DELETE FROM ingestion_findings WHERE tenant_id = '$tenantId' AND ingestion_run_id IN (
  SELECT id FROM ingestion_runs WHERE tenant_id = '$tenantId' AND data_source_id IN (
    SELECT id FROM data_sources WHERE tenant_id = '$tenantId' AND name LIKE 'Browser replay e2e-%'
  )
);
DELETE FROM ingestion_runs WHERE tenant_id = '$tenantId' AND data_source_id IN (
  SELECT id FROM data_sources WHERE tenant_id = '$tenantId' AND name LIKE 'Browser replay e2e-%'
);
DELETE FROM source_version_operations WHERE tenant_id = '$tenantId' AND source_version_id IN (
  SELECT sv.id FROM source_versions sv JOIN source_assets sa ON sa.id = sv.source_asset_id
  WHERE sa.data_source_id IN (SELECT id FROM data_sources WHERE tenant_id = '$tenantId' AND name LIKE 'Browser replay e2e-%')
);
DELETE FROM audit_events WHERE tenant_id = '$tenantId' AND resource_type = 'source_version' AND resource_id IN (
  SELECT sv.id FROM source_versions sv JOIN source_assets sa ON sa.id = sv.source_asset_id
  WHERE sa.data_source_id IN (SELECT id FROM data_sources WHERE tenant_id = '$tenantId' AND name LIKE 'Browser replay e2e-%')
);
ALTER TABLE source_version_quarantine_decisions DISABLE TRIGGER immutable_source_version_quarantine_decisions;
DELETE FROM source_version_quarantine_decisions WHERE tenant_id = '$tenantId' AND source_version_id IN (
  SELECT sv.id FROM source_versions sv JOIN source_assets sa ON sa.id = sv.source_asset_id
  WHERE sa.data_source_id IN (SELECT id FROM data_sources WHERE tenant_id = '$tenantId' AND name LIKE 'Browser replay e2e-%')
);
ALTER TABLE source_version_quarantine_decisions ENABLE TRIGGER immutable_source_version_quarantine_decisions;
DELETE FROM source_versions WHERE tenant_id = '$tenantId' AND source_asset_id IN (
  SELECT id FROM source_assets WHERE data_source_id IN (
    SELECT id FROM data_sources WHERE tenant_id = '$tenantId' AND name LIKE 'Browser replay e2e-%'
  )
);
DELETE FROM source_assets WHERE tenant_id = '$tenantId' AND data_source_id IN (
  SELECT id FROM data_sources WHERE tenant_id = '$tenantId' AND name LIKE 'Browser replay e2e-%'
);
DELETE FROM data_sources WHERE tenant_id = '$tenantId' AND name LIKE 'Browser replay e2e-%';
COMMIT;
"@
  Invoke-RecoverySql $fixtureCleanup

  $entityCleanup = @"
BEGIN;
CREATE TEMP TABLE browser_fixture_entities (id varchar(36) PRIMARY KEY) ON COMMIT DROP;
INSERT INTO browser_fixture_entities
SELECT id FROM entities WHERE tenant_id = '$tenantId' AND attributes ->> 'acceptance_fixture' = 'true';
CREATE TEMP TABLE browser_fixture_comparison_sets (id varchar(36) PRIMARY KEY) ON COMMIT DROP;
INSERT INTO browser_fixture_comparison_sets
SELECT DISTINCT comparison_set_id FROM comparison_set_members WHERE tenant_id = '$tenantId'
  AND entity_id IN (SELECT id FROM browser_fixture_entities);
ALTER TABLE workspace_export_events DISABLE TRIGGER immutable_workspace_export_events;
DELETE FROM workspace_export_events WHERE tenant_id = '$tenantId'
  AND comparison_set_id IN (SELECT id FROM browser_fixture_comparison_sets);
ALTER TABLE workspace_export_events ENABLE TRIGGER immutable_workspace_export_events;
DELETE FROM audit_events WHERE tenant_id = '$tenantId' AND resource_type = 'comparison_set'
  AND resource_id IN (SELECT id FROM browser_fixture_comparison_sets);
DELETE FROM comparison_set_members WHERE tenant_id = '$tenantId'
  AND comparison_set_id IN (SELECT id FROM browser_fixture_comparison_sets);
ALTER TABLE comparison_set_versions DISABLE TRIGGER immutable_comparison_set_versions;
DELETE FROM comparison_set_versions WHERE tenant_id = '$tenantId'
  AND comparison_set_id IN (SELECT id FROM browser_fixture_comparison_sets);
ALTER TABLE comparison_set_versions ENABLE TRIGGER immutable_comparison_set_versions;
DELETE FROM comparison_sets WHERE tenant_id = '$tenantId' AND id IN (SELECT id FROM browser_fixture_comparison_sets);
DELETE FROM regulatory_events WHERE tenant_id = '$tenantId' AND (
  subject_entity_id IN (SELECT id FROM browser_fixture_entities)
  OR indication_entity_id IN (SELECT id FROM browser_fixture_entities)
  OR organization_entity_id IN (SELECT id FROM browser_fixture_entities)
);
DELETE FROM epidemiology_observations WHERE tenant_id = '$tenantId' AND (
  disease_entity_id IN (SELECT id FROM browser_fixture_entities)
  OR publisher_entity_id IN (SELECT id FROM browser_fixture_entities)
);
DELETE FROM patient_population_entity_links WHERE tenant_id = '$tenantId' AND (
  entity_id IN (SELECT id FROM browser_fixture_entities)
  OR patient_population_id IN (
    SELECT id FROM patient_populations
    WHERE tenant_id = '$tenantId' AND attributes ->> 'acceptance_fixture' = 'true'
  )
);
DELETE FROM patient_populations
WHERE tenant_id = '$tenantId' AND attributes ->> 'acceptance_fixture' = 'true';
DELETE FROM deal_rights WHERE tenant_id = '$tenantId' AND deal_id IN (
  SELECT id FROM deal_profiles WHERE tenant_id = '$tenantId' AND entity_id IN (SELECT id FROM browser_fixture_entities)
);
DELETE FROM deal_asset_associations WHERE tenant_id = '$tenantId' AND deal_id IN (
  SELECT id FROM deal_profiles WHERE tenant_id = '$tenantId' AND entity_id IN (SELECT id FROM browser_fixture_entities)
);
DELETE FROM deal_party_associations WHERE tenant_id = '$tenantId' AND deal_id IN (
  SELECT id FROM deal_profiles WHERE tenant_id = '$tenantId' AND entity_id IN (SELECT id FROM browser_fixture_entities)
);
DELETE FROM deal_profiles WHERE tenant_id = '$tenantId' AND entity_id IN (SELECT id FROM browser_fixture_entities);
ALTER TABLE development_program_organizations DISABLE TRIGGER immutable_development_program_organizations;
DELETE FROM development_program_organizations WHERE tenant_id = '$tenantId' AND program_id IN (
  SELECT id FROM development_programs WHERE tenant_id = '$tenantId' AND (
    drug_entity_id IN (SELECT id FROM browser_fixture_entities)
    OR target_entity_id IN (SELECT id FROM browser_fixture_entities)
    OR disease_entity_id IN (SELECT id FROM browser_fixture_entities)
    OR organization_entity_id IN (SELECT id FROM browser_fixture_entities)
  )
);
ALTER TABLE development_program_organizations ENABLE TRIGGER immutable_development_program_organizations;
ALTER TABLE development_program_targets DISABLE TRIGGER immutable_development_program_targets;
DELETE FROM development_program_targets WHERE tenant_id = '$tenantId' AND program_id IN (
  SELECT id FROM development_programs WHERE tenant_id = '$tenantId' AND (
    drug_entity_id IN (SELECT id FROM browser_fixture_entities)
    OR target_entity_id IN (SELECT id FROM browser_fixture_entities)
    OR disease_entity_id IN (SELECT id FROM browser_fixture_entities)
    OR organization_entity_id IN (SELECT id FROM browser_fixture_entities)
  )
);
ALTER TABLE development_program_targets ENABLE TRIGGER immutable_development_program_targets;
DELETE FROM development_programs WHERE tenant_id = '$tenantId' AND (
  drug_entity_id IN (SELECT id FROM browser_fixture_entities)
  OR target_entity_id IN (SELECT id FROM browser_fixture_entities)
  OR disease_entity_id IN (SELECT id FROM browser_fixture_entities)
  OR organization_entity_id IN (SELECT id FROM browser_fixture_entities)
);
DELETE FROM clinical_trial_result_disclosures WHERE tenant_id = '$tenantId' AND trial_id IN (
  SELECT id FROM clinical_trial_profiles WHERE tenant_id = '$tenantId' AND entity_id IN (SELECT id FROM browser_fixture_entities)
);
DELETE FROM clinical_trial_entity_roles WHERE tenant_id = '$tenantId' AND (
  entity_id IN (SELECT id FROM browser_fixture_entities)
  OR trial_id IN (SELECT id FROM clinical_trial_profiles WHERE tenant_id = '$tenantId' AND entity_id IN (SELECT id FROM browser_fixture_entities))
);
DELETE FROM clinical_trial_profiles WHERE tenant_id = '$tenantId' AND entity_id IN (SELECT id FROM browser_fixture_entities);
DELETE FROM patent_families WHERE tenant_id = '$tenantId' AND entity_id IN (SELECT id FROM browser_fixture_entities);
DELETE FROM compound_structures WHERE tenant_id = '$tenantId' AND entity_id IN (SELECT id FROM browser_fixture_entities);
DELETE FROM news_events WHERE tenant_id = '$tenantId' AND event_identifier LIKE 'E2E-e2e-%';
DELETE FROM projection_deliveries WHERE outbox_event_id IN (
  SELECT id FROM outbox_events WHERE tenant_id = '$tenantId' AND aggregate_type = 'entity'
    AND aggregate_id IN (SELECT id FROM browser_fixture_entities)
);
DELETE FROM outbox_events WHERE tenant_id = '$tenantId' AND aggregate_type = 'entity'
  AND aggregate_id IN (SELECT id FROM browser_fixture_entities);
ALTER TABLE entity_resolution_decisions DISABLE TRIGGER immutable_entity_resolution_decisions;
DELETE FROM entity_resolution_decisions WHERE tenant_id = '$tenantId' AND resolution_case_id IN (
  SELECT id FROM entity_resolution_cases WHERE tenant_id = '$tenantId' AND (
    source_entity_id IN (SELECT id FROM browser_fixture_entities)
    OR candidate_entity_id IN (SELECT id FROM browser_fixture_entities)
  )
);
ALTER TABLE entity_resolution_decisions ENABLE TRIGGER immutable_entity_resolution_decisions;
DELETE FROM entity_canonical_links WHERE tenant_id = '$tenantId' AND (
  alias_entity_id IN (SELECT id FROM browser_fixture_entities)
  OR canonical_entity_id IN (SELECT id FROM browser_fixture_entities)
);
DELETE FROM entity_resolution_cases WHERE tenant_id = '$tenantId' AND (
  source_entity_id IN (SELECT id FROM browser_fixture_entities)
  OR candidate_entity_id IN (SELECT id FROM browser_fixture_entities)
);
DELETE FROM target_profiles WHERE tenant_id = '$tenantId' AND entity_id IN (SELECT id FROM browser_fixture_entities);
DELETE FROM entity_ontology_mappings WHERE tenant_id = '$tenantId' AND entity_id IN (SELECT id FROM browser_fixture_entities);
DELETE FROM entity_identifiers WHERE tenant_id = '$tenantId' AND entity_id IN (SELECT id FROM browser_fixture_entities);
DELETE FROM source_documents WHERE tenant_id = '$tenantId' AND title LIKE 'Browser publication e2e-%';
DELETE FROM entity_aliases WHERE tenant_id = '$tenantId' AND entity_id IN (SELECT id FROM browser_fixture_entities);
DELETE FROM entities WHERE tenant_id = '$tenantId' AND id IN (SELECT id FROM browser_fixture_entities);
COMMIT;
"@
  Invoke-RecoverySql $entityCleanup

  $accountCleanup = @"
BEGIN;
CREATE TEMP TABLE browser_account_comparison_sets (id varchar(36) PRIMARY KEY) ON COMMIT DROP;
INSERT INTO browser_account_comparison_sets
SELECT id FROM comparison_sets WHERE tenant_id = '$tenantId'
  AND owner_user_id IN (SELECT id FROM users WHERE normalized_email LIKE 'e2e-%@example.test');
ALTER TABLE workspace_export_events DISABLE TRIGGER immutable_workspace_export_events;
DELETE FROM workspace_export_events WHERE tenant_id = '$tenantId'
  AND comparison_set_id IN (SELECT id FROM browser_account_comparison_sets);
DELETE FROM workspace_export_events WHERE tenant_id = '$tenantId'
  AND requested_by_user_id IN (SELECT id FROM users WHERE normalized_email LIKE 'e2e-%@example.test');
ALTER TABLE workspace_export_events ENABLE TRIGGER immutable_workspace_export_events;
DELETE FROM audit_events WHERE tenant_id = '$tenantId' AND resource_type = 'comparison_set'
  AND resource_id IN (SELECT id FROM browser_account_comparison_sets);
DELETE FROM comparison_set_members WHERE tenant_id = '$tenantId'
  AND comparison_set_id IN (SELECT id FROM browser_account_comparison_sets);
ALTER TABLE comparison_set_versions DISABLE TRIGGER immutable_comparison_set_versions;
DELETE FROM comparison_set_versions WHERE tenant_id = '$tenantId'
  AND comparison_set_id IN (SELECT id FROM browser_account_comparison_sets);
ALTER TABLE comparison_set_versions ENABLE TRIGGER immutable_comparison_set_versions;
DELETE FROM comparison_sets WHERE tenant_id = '$tenantId' AND id IN (SELECT id FROM browser_account_comparison_sets);
DELETE FROM workspace_export_policies WHERE tenant_id = '$tenantId'
  AND policy_version = 'browser-domain-export-v1'
  AND configured_by_user_id IN (SELECT id FROM users WHERE normalized_email LIKE 'e2e-%@example.test');
ALTER TABLE monitoring_alerts DISABLE TRIGGER immutable_monitoring_alerts;
ALTER TABLE saved_search_versions DISABLE TRIGGER immutable_saved_search_versions;
DELETE FROM monitoring_alert_receipts WHERE tenant_id = '$tenantId'
  AND user_id IN (SELECT id FROM users WHERE normalized_email LIKE 'e2e-%@example.test');
DELETE FROM monitoring_alerts WHERE tenant_id = '$tenantId'
  AND recipient_user_id IN (SELECT id FROM users WHERE normalized_email LIKE 'e2e-%@example.test');
DELETE FROM monitoring_topics WHERE tenant_id = '$tenantId'
  AND owner_user_id IN (SELECT id FROM users WHERE normalized_email LIKE 'e2e-%@example.test');
DELETE FROM saved_search_versions WHERE tenant_id = '$tenantId' AND saved_search_id IN (
  SELECT id FROM saved_searches WHERE tenant_id = '$tenantId'
    AND owner_user_id IN (SELECT id FROM users WHERE normalized_email LIKE 'e2e-%@example.test')
);
DELETE FROM saved_searches WHERE tenant_id = '$tenantId'
  AND owner_user_id IN (SELECT id FROM users WHERE normalized_email LIKE 'e2e-%@example.test');
ALTER TABLE monitoring_alerts ENABLE TRIGGER immutable_monitoring_alerts;
ALTER TABLE saved_search_versions ENABLE TRIGGER immutable_saved_search_versions;
DELETE FROM user_sessions WHERE tenant_id = '$tenantId'
  AND user_id IN (SELECT id FROM users WHERE normalized_email LIKE 'e2e-%@example.test');
DELETE FROM users WHERE tenant_id = '$tenantId' AND normalized_email LIKE 'e2e-%@example.test';
COMMIT;
"@
  Invoke-RecoverySql $accountCleanup

  $indexPrefix = (& $docker compose -f $compose exec -T worker sh -ec 'printf %s "${OPENSEARCH_INDEX_PREFIX:-pharma}"').Trim()
  if ($indexPrefix -notmatch '^[a-z0-9][a-z0-9-]{0,79}$') {
    throw 'Runtime returned an unsafe OpenSearch index prefix.'
  }
  foreach ($fixtureId in $fixtureIds) {
    $deleteResult = (& $docker compose -f $compose exec -T opensearch curl --silent --show-error --request DELETE "http://127.0.0.1:9200/$indexPrefix-entities-write/_doc/$tenantId`:$fixtureId`?routing=$tenantId&refresh=true").Trim()
    if ($LASTEXITCODE -ne 0) {
      throw "OpenSearch fixture cleanup failed for $fixtureId."
    }
    $deletePayload = $deleteResult | ConvertFrom-Json
    if ($deletePayload.result -notin @('deleted', 'not_found')) {
      throw "OpenSearch returned an unexpected fixture cleanup result for $fixtureId."
    }
  }

  $afterAccounts = ((& $docker compose -f $compose exec -T postgres psql -X -U $postgresUser -d $postgresDatabase -At -v ON_ERROR_STOP=1 -c "SELECT count(*) FROM users WHERE tenant_id = '$tenantId' AND normalized_email LIKE 'e2e-%@example.test'").Trim())
  $afterFixtures = ((& $docker compose -f $compose exec -T postgres psql -X -U $postgresUser -d $postgresDatabase -At -v ON_ERROR_STOP=1 -c "SELECT (SELECT count(*) FROM entities WHERE tenant_id = '$tenantId' AND attributes ->> 'acceptance_fixture' = 'true') + (SELECT count(*) FROM patient_populations WHERE tenant_id = '$tenantId' AND attributes ->> 'acceptance_fixture' = 'true')").Trim())
  if ($afterAccounts -ne '0' -or $afterFixtures -ne '0') {
    throw 'Recovery completed with remaining temporary browser state.'
  }

  [ordered]@{
    status = 'passed'
    backup_sha256 = $BackupSha256
    temporary_accounts_before = [int]$beforeAccounts
    temporary_accounts_after = [int]$afterAccounts
    temporary_entities_before = [int]$beforeFixtures
    temporary_entities_after = [int]$afterFixtures
  } | ConvertTo-Json -Compress
} finally {
  $env:DOCKER_CONTEXT = $previousContext
}
