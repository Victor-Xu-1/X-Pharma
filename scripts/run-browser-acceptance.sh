#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT_DIR"
output_path=""
update_snapshots=false
browser_target=chrome
keep_browser_output=${PHARMA_BROWSER_KEEP_OUTPUT:-false}
browser_workers=${PHARMA_BROWSER_WORKERS:-4}
recover_interrupted_run=false

usage() {
  cat <<'EOF'
Usage: run-browser-acceptance.sh [--browser chrome|edge-current|edge-previous] [--output FILE] [--update-snapshots] [--recover-interrupted-run]

Run the real wide desktop, desktop, tablet and mobile browser acceptance suite
against the local authenticated runtime. The optional report never contains test credentials.
Snapshot updates are an explicit review operation and cannot produce release evidence.
Chrome owns the visual baseline. Edge targets compare against it but cannot update it.
--recover-interrupted-run removes only browser acceptance fixtures and temporary e2e accounts left by an interrupted run.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --output)
      [[ $# -ge 2 ]] || { echo "--output requires a value" >&2; exit 2; }
      output_path=$2
      shift 2
      ;;
    --update-snapshots)
      update_snapshots=true
      shift
      ;;
    --browser)
      [[ $# -ge 2 ]] || { echo "--browser requires a value" >&2; exit 2; }
      browser_target=$2
      shift 2
      ;;
    --recover-interrupted-run)
      recover_interrupted_run=true
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

[[ $browser_target == chrome || $browser_target == edge-current || $browser_target == edge-previous ]] || {
  echo "--browser must be chrome, edge-current or edge-previous" >&2
  exit 2
}
[[ $keep_browser_output == true || $keep_browser_output == false ]] || {
  echo "PHARMA_BROWSER_KEEP_OUTPUT must be true or false" >&2
  exit 2
}
[[ "$browser_workers" =~ ^[1-9][0-9]*$ && "$browser_workers" -le 16 ]] || {
  echo "PHARMA_BROWSER_WORKERS must be an integer from 1 to 16" >&2
  exit 2
}

if [[ "$update_snapshots" == true && -n "$output_path" ]]; then
  echo "--update-snapshots cannot be combined with --output" >&2
  exit 2
fi
if [[ "$recover_interrupted_run" == true && ( "$update_snapshots" == true || -n "$output_path" ) ]]; then
  echo "--recover-interrupted-run cannot be combined with --output or --update-snapshots" >&2
  exit 2
fi
if [[ "$update_snapshots" == true && "$browser_target" != chrome ]]; then
  echo "Only Google Chrome may update the repository visual baseline" >&2
  exit 2
fi

for command in curl docker node openssl python3 realpath dirname basename; do
  command -v "$command" >/dev/null 2>&1 || {
    echo "required command is unavailable: $command" >&2
    exit 1
  }
done

if [[ -z "${COMPOSE_FILE:-}" ]]; then
  if [[ -n "${MSYSTEM:-}" ]]; then
    export COMPOSE_FILE="compose.yaml;compose.dev.yaml;compose.telemetry.yaml"
  else
    export COMPOSE_FILE="compose.yaml:compose.dev.yaml:compose.telemetry.yaml"
  fi
fi
export SEARCH_ALLOW_NON_AUTHORITATIVE_PROJECTION=true
source "$ROOT_DIR/scripts/lib/browser_fonts.sh"
source "$ROOT_DIR/scripts/lib/browser_runtime_health.sh"
verify_browser_fonts

api_container_id=$(docker compose ps -q api)
if [[ -z "$api_container_id" ]]; then
  echo "The local API container is not running in the selected Docker daemon" >&2
  exit 1
fi
api_runtime_state=$(
  docker inspect --format '{{.State.Running}} {{if .State.Health}}{{.State.Health.Status}}{{else}}missing{{end}}' \
    "$api_container_id"
)
if [[ "$api_runtime_state" != true\ * ]]; then
  echo "The local API container is not running in the selected Docker daemon: $api_runtime_state" >&2
  exit 1
fi
if [[ "$api_runtime_state" != "true healthy" && "$recover_interrupted_run" != true ]]; then
  wait_for_browser_container_healthy "$api_container_id" api 30 || exit 1
fi

package_manager=$(node -p "require('./apps/web/package.json').packageManager")
if [[ ! "$package_manager" =~ ^pnpm@[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "apps/web/package.json must pin packageManager to an exact pnpm version" >&2
  exit 1
fi

pg_user=$(docker compose exec -T postgres printenv POSTGRES_USER | tr -d '\r')
pg_db=$(docker compose exec -T postgres printenv POSTGRES_DB | tr -d '\r')
tenant_record=$(
  docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -At -v ON_ERROR_STOP=1 \
    -F '|' -c "SELECT id, slug FROM tenants ORDER BY created_at, id LIMIT 1"
)
IFS='|' read -r tenant_id tenant_slug <<< "$tenant_record"
if [[ ! "$tenant_id" =~ ^[0-9a-f-]{36}$ || -z "$tenant_slug" ]]; then
  echo "No tenant exists for browser acceptance" >&2
  exit 1
fi
opensearch_index_prefix=$(
  docker compose exec -T worker sh -ec 'printf %s "${OPENSEARCH_INDEX_PREFIX:-pharma}"'
)
[[ "$opensearch_index_prefix" =~ ^[a-z0-9][a-z0-9-]{0,79}$ ]] || {
  echo "Runtime returned an unsafe OpenSearch index prefix" >&2
  exit 1
}

run_id="$(date -u +%Y%m%d%H%M%S)-$RANDOM"
browser_projects=(desktop-1440 desktop-1920 tablet-1024 mobile-390)
email_prefix="e2e-$run_id"
email_pattern="e2e-%@example.test"
password="$(openssl rand -hex 24)Aa1!"
fixture_key="e2e-$run_id"
output_dir="/tmp/pharma-browser-acceptance-$$"
if [[ -n "${MSYSTEM:-}" ]]; then
  mkdir "$output_dir"
else
  mkdir -m 0700 "$output_dir"
fi
fixture_source_root="$ROOT_DIR/data/sources/empty/.browser-$fixture_key"
fixture_ids_path="$output_dir/fixture-ids"
touch "$fixture_ids_path"
if [[ -z "${MSYSTEM:-}" ]]; then chmod 600 "$fixture_ids_path"; fi
projection_ids_path="$output_dir/projection-ids"
touch "$projection_ids_path"
if [[ -z "${MSYSTEM:-}" ]]; then chmod 600 "$projection_ids_path"; fi
policy_snapshot=""
export_policy_installed=false
cleanup_completed=false
cleanup_account() {
  if [[ "$export_policy_installed" == true ]]; then
    if [[ -n "$policy_snapshot" ]]; then
      docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -v ON_ERROR_STOP=1 \
        -v tenant_id="$tenant_id" -v email_pattern="$email_pattern" -v policy_snapshot="$policy_snapshot" >/dev/null <<'SQL'
BEGIN;
CREATE TEMP TABLE browser_account_comparison_sets (id varchar(36) PRIMARY KEY) ON COMMIT DROP;
INSERT INTO browser_account_comparison_sets
SELECT id FROM comparison_sets
WHERE tenant_id = :'tenant_id'
  AND owner_user_id IN (SELECT id FROM users WHERE normalized_email LIKE :'email_pattern');
ALTER TABLE workspace_export_events DISABLE TRIGGER immutable_workspace_export_events;
DELETE FROM workspace_export_events
WHERE tenant_id = :'tenant_id'
  AND comparison_set_id IN (SELECT id FROM browser_account_comparison_sets);
ALTER TABLE workspace_export_events ENABLE TRIGGER immutable_workspace_export_events;
DELETE FROM audit_events
WHERE tenant_id = :'tenant_id'
  AND resource_type = 'comparison_set'
  AND resource_id IN (SELECT id FROM browser_account_comparison_sets);
DELETE FROM comparison_set_members
WHERE tenant_id = :'tenant_id'
  AND comparison_set_id IN (SELECT id FROM browser_account_comparison_sets);
ALTER TABLE comparison_set_versions DISABLE TRIGGER immutable_comparison_set_versions;
DELETE FROM comparison_set_versions
WHERE tenant_id = :'tenant_id'
  AND comparison_set_id IN (SELECT id FROM browser_account_comparison_sets);
ALTER TABLE comparison_set_versions ENABLE TRIGGER immutable_comparison_set_versions;
DELETE FROM comparison_sets
WHERE tenant_id = :'tenant_id'
  AND id IN (SELECT id FROM browser_account_comparison_sets);
ALTER TABLE workspace_export_events DISABLE TRIGGER immutable_workspace_export_events;
DELETE FROM workspace_export_events
WHERE tenant_id = :'tenant_id'
  AND requested_by_user_id IN (SELECT id FROM users WHERE normalized_email LIKE :'email_pattern');
ALTER TABLE workspace_export_events ENABLE TRIGGER immutable_workspace_export_events;
DELETE FROM workspace_export_policies WHERE tenant_id = :'tenant_id';
INSERT INTO workspace_export_policies
SELECT (json_populate_record(NULL::workspace_export_policies, :'policy_snapshot'::json)).*;
ALTER TABLE monitoring_alerts DISABLE TRIGGER immutable_monitoring_alerts;
ALTER TABLE saved_search_versions DISABLE TRIGGER immutable_saved_search_versions;
DELETE FROM monitoring_alert_receipts
WHERE tenant_id = :'tenant_id'
  AND user_id IN (SELECT id FROM users WHERE normalized_email LIKE :'email_pattern');
DELETE FROM monitoring_alerts
WHERE tenant_id = :'tenant_id'
  AND recipient_user_id IN (SELECT id FROM users WHERE normalized_email LIKE :'email_pattern');
DELETE FROM monitoring_topics
WHERE tenant_id = :'tenant_id'
  AND owner_user_id IN (SELECT id FROM users WHERE normalized_email LIKE :'email_pattern');
DELETE FROM saved_search_versions
WHERE tenant_id = :'tenant_id'
  AND saved_search_id IN (
    SELECT id FROM saved_searches
    WHERE tenant_id = :'tenant_id'
      AND owner_user_id IN (SELECT id FROM users WHERE normalized_email LIKE :'email_pattern')
  );
DELETE FROM saved_searches
WHERE tenant_id = :'tenant_id'
  AND owner_user_id IN (SELECT id FROM users WHERE normalized_email LIKE :'email_pattern');
ALTER TABLE monitoring_alerts ENABLE TRIGGER immutable_monitoring_alerts;
ALTER TABLE saved_search_versions ENABLE TRIGGER immutable_saved_search_versions;
DELETE FROM user_sessions
WHERE tenant_id = :'tenant_id'
  AND user_id IN (SELECT id FROM users WHERE normalized_email LIKE :'email_pattern');
DELETE FROM account_invitations WHERE created_by_user_id IN (SELECT id FROM users WHERE normalized_email LIKE :'email_pattern')
  OR claimed_user_id IN (SELECT id FROM users WHERE normalized_email LIKE :'email_pattern');
DELETE FROM user_sessions WHERE user_id IN (SELECT id FROM users WHERE normalized_email LIKE :'email_pattern');
DELETE FROM organization_memberships WHERE user_id IN (SELECT id FROM users WHERE normalized_email LIKE :'email_pattern');
DELETE FROM users WHERE normalized_email LIKE :'email_pattern';
COMMIT;
SQL
    else
      docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -v ON_ERROR_STOP=1 \
        -v tenant_id="$tenant_id" -v email_pattern="$email_pattern" >/dev/null <<'SQL'
BEGIN;
CREATE TEMP TABLE browser_account_comparison_sets (id varchar(36) PRIMARY KEY) ON COMMIT DROP;
INSERT INTO browser_account_comparison_sets
SELECT id FROM comparison_sets
WHERE tenant_id = :'tenant_id'
  AND owner_user_id IN (SELECT id FROM users WHERE normalized_email LIKE :'email_pattern');
ALTER TABLE workspace_export_events DISABLE TRIGGER immutable_workspace_export_events;
DELETE FROM workspace_export_events
WHERE tenant_id = :'tenant_id'
  AND comparison_set_id IN (SELECT id FROM browser_account_comparison_sets);
ALTER TABLE workspace_export_events ENABLE TRIGGER immutable_workspace_export_events;
DELETE FROM audit_events
WHERE tenant_id = :'tenant_id'
  AND resource_type = 'comparison_set'
  AND resource_id IN (SELECT id FROM browser_account_comparison_sets);
DELETE FROM comparison_set_members
WHERE tenant_id = :'tenant_id'
  AND comparison_set_id IN (SELECT id FROM browser_account_comparison_sets);
ALTER TABLE comparison_set_versions DISABLE TRIGGER immutable_comparison_set_versions;
DELETE FROM comparison_set_versions
WHERE tenant_id = :'tenant_id'
  AND comparison_set_id IN (SELECT id FROM browser_account_comparison_sets);
ALTER TABLE comparison_set_versions ENABLE TRIGGER immutable_comparison_set_versions;
DELETE FROM comparison_sets
WHERE tenant_id = :'tenant_id'
  AND id IN (SELECT id FROM browser_account_comparison_sets);
ALTER TABLE workspace_export_events DISABLE TRIGGER immutable_workspace_export_events;
DELETE FROM workspace_export_events
WHERE tenant_id = :'tenant_id'
  AND requested_by_user_id IN (SELECT id FROM users WHERE normalized_email LIKE :'email_pattern');
ALTER TABLE workspace_export_events ENABLE TRIGGER immutable_workspace_export_events;
DELETE FROM workspace_export_policies WHERE tenant_id = :'tenant_id';
ALTER TABLE monitoring_alerts DISABLE TRIGGER immutable_monitoring_alerts;
ALTER TABLE saved_search_versions DISABLE TRIGGER immutable_saved_search_versions;
DELETE FROM monitoring_alert_receipts
WHERE tenant_id = :'tenant_id'
  AND user_id IN (SELECT id FROM users WHERE normalized_email LIKE :'email_pattern');
DELETE FROM monitoring_alerts
WHERE tenant_id = :'tenant_id'
  AND recipient_user_id IN (SELECT id FROM users WHERE normalized_email LIKE :'email_pattern');
DELETE FROM monitoring_topics
WHERE tenant_id = :'tenant_id'
  AND owner_user_id IN (SELECT id FROM users WHERE normalized_email LIKE :'email_pattern');
DELETE FROM saved_search_versions
WHERE tenant_id = :'tenant_id'
  AND saved_search_id IN (
    SELECT id FROM saved_searches
    WHERE tenant_id = :'tenant_id'
      AND owner_user_id IN (SELECT id FROM users WHERE normalized_email LIKE :'email_pattern')
  );
DELETE FROM saved_searches
WHERE tenant_id = :'tenant_id'
  AND owner_user_id IN (SELECT id FROM users WHERE normalized_email LIKE :'email_pattern');
ALTER TABLE monitoring_alerts ENABLE TRIGGER immutable_monitoring_alerts;
ALTER TABLE saved_search_versions ENABLE TRIGGER immutable_saved_search_versions;
DELETE FROM user_sessions
WHERE tenant_id = :'tenant_id'
  AND user_id IN (SELECT id FROM users WHERE normalized_email LIKE :'email_pattern');
DELETE FROM account_invitations WHERE created_by_user_id IN (SELECT id FROM users WHERE normalized_email LIKE :'email_pattern')
  OR claimed_user_id IN (SELECT id FROM users WHERE normalized_email LIKE :'email_pattern');
DELETE FROM user_sessions WHERE user_id IN (SELECT id FROM users WHERE normalized_email LIKE :'email_pattern');
DELETE FROM organization_memberships WHERE user_id IN (SELECT id FROM users WHERE normalized_email LIKE :'email_pattern');
DELETE FROM users WHERE normalized_email LIKE :'email_pattern';
COMMIT;
SQL
    fi
    export_policy_installed=false
    return
  fi
  docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -v ON_ERROR_STOP=1 >/dev/null <<SQL
BEGIN;
CREATE TEMP TABLE browser_account_comparison_sets (id varchar(36) PRIMARY KEY) ON COMMIT DROP;
INSERT INTO browser_account_comparison_sets
SELECT id FROM comparison_sets
WHERE tenant_id = '$tenant_id'
  AND owner_user_id IN (SELECT id FROM users WHERE normalized_email LIKE '$email_pattern');
ALTER TABLE workspace_export_events DISABLE TRIGGER immutable_workspace_export_events;
DELETE FROM workspace_export_events
WHERE tenant_id = '$tenant_id'
  AND comparison_set_id IN (SELECT id FROM browser_account_comparison_sets);
ALTER TABLE workspace_export_events ENABLE TRIGGER immutable_workspace_export_events;
DELETE FROM audit_events
WHERE tenant_id = '$tenant_id'
  AND resource_type = 'comparison_set'
  AND resource_id IN (SELECT id FROM browser_account_comparison_sets);
DELETE FROM comparison_set_members
WHERE tenant_id = '$tenant_id'
  AND comparison_set_id IN (SELECT id FROM browser_account_comparison_sets);
ALTER TABLE comparison_set_versions DISABLE TRIGGER immutable_comparison_set_versions;
DELETE FROM comparison_set_versions
WHERE tenant_id = '$tenant_id'
  AND comparison_set_id IN (SELECT id FROM browser_account_comparison_sets);
ALTER TABLE comparison_set_versions ENABLE TRIGGER immutable_comparison_set_versions;
DELETE FROM comparison_sets
WHERE tenant_id = '$tenant_id'
  AND id IN (SELECT id FROM browser_account_comparison_sets);
ALTER TABLE workspace_export_events DISABLE TRIGGER immutable_workspace_export_events;
DELETE FROM workspace_export_events
WHERE tenant_id = '$tenant_id'
  AND requested_by_user_id IN (SELECT id FROM users WHERE normalized_email LIKE '$email_pattern');
ALTER TABLE workspace_export_events ENABLE TRIGGER immutable_workspace_export_events;
DELETE FROM workspace_export_policies
WHERE tenant_id = '$tenant_id'
  AND policy_version = 'browser-domain-export-v1'
  AND configured_by_user_id IN (SELECT id FROM users WHERE normalized_email LIKE '$email_pattern');
ALTER TABLE monitoring_alerts DISABLE TRIGGER immutable_monitoring_alerts;
ALTER TABLE saved_search_versions DISABLE TRIGGER immutable_saved_search_versions;
DELETE FROM monitoring_alert_receipts
WHERE tenant_id = '$tenant_id'
  AND user_id IN (SELECT id FROM users WHERE normalized_email LIKE '$email_pattern');
DELETE FROM monitoring_alerts
WHERE tenant_id = '$tenant_id'
  AND recipient_user_id IN (SELECT id FROM users WHERE normalized_email LIKE '$email_pattern');
DELETE FROM monitoring_topics
WHERE tenant_id = '$tenant_id'
  AND owner_user_id IN (SELECT id FROM users WHERE normalized_email LIKE '$email_pattern');
DELETE FROM saved_search_versions
WHERE tenant_id = '$tenant_id'
  AND saved_search_id IN (
    SELECT id FROM saved_searches
    WHERE tenant_id = '$tenant_id'
      AND owner_user_id IN (SELECT id FROM users WHERE normalized_email LIKE '$email_pattern')
  );
DELETE FROM saved_searches
WHERE tenant_id = '$tenant_id'
  AND owner_user_id IN (SELECT id FROM users WHERE normalized_email LIKE '$email_pattern');
ALTER TABLE monitoring_alerts ENABLE TRIGGER immutable_monitoring_alerts;
ALTER TABLE saved_search_versions ENABLE TRIGGER immutable_saved_search_versions;
DELETE FROM user_sessions
WHERE tenant_id = '$tenant_id'
  AND user_id IN (SELECT id FROM users WHERE normalized_email LIKE '$email_pattern');
DELETE FROM account_invitations WHERE created_by_user_id IN (SELECT id FROM users WHERE normalized_email LIKE '$email_pattern')
  OR claimed_user_id IN (SELECT id FROM users WHERE normalized_email LIKE '$email_pattern');
DELETE FROM user_sessions WHERE user_id IN (SELECT id FROM users WHERE normalized_email LIKE '$email_pattern');
DELETE FROM organization_memberships WHERE user_id IN (SELECT id FROM users WHERE normalized_email LIKE '$email_pattern');
DELETE FROM users WHERE normalized_email LIKE '$email_pattern';
COMMIT;
SQL
}
cleanup_fixtures() {
  docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -v ON_ERROR_STOP=1 >/dev/null <<SQL
BEGIN;
CREATE TEMP TABLE browser_evidence_facts (id varchar(36) PRIMARY KEY, resource_id varchar(36)) ON COMMIT DROP;
INSERT INTO browser_evidence_facts
SELECT id, published_resource_id
FROM staged_facts
WHERE tenant_id = '$tenant_id' AND fact_key LIKE 'browser-evidence-e2e-%';
CREATE TEMP TABLE browser_knowledge_pages (id varchar(36) PRIMARY KEY) ON COMMIT DROP;
INSERT INTO browser_knowledge_pages
SELECT id
FROM knowledge_pages
WHERE tenant_id = '$tenant_id' AND page_key LIKE 'browser/e2e-%';
ALTER TABLE knowledge_links DISABLE TRIGGER immutable_knowledge_links;
ALTER TABLE knowledge_citations DISABLE TRIGGER immutable_knowledge_citations;
ALTER TABLE knowledge_page_versions DISABLE TRIGGER immutable_knowledge_page_versions;
DELETE FROM knowledge_links
WHERE tenant_id = '$tenant_id'
  AND page_version_id IN (
    SELECT id FROM knowledge_page_versions WHERE knowledge_page_id IN (SELECT id FROM browser_knowledge_pages)
  );
DELETE FROM knowledge_citations
WHERE tenant_id = '$tenant_id'
  AND page_version_id IN (
    SELECT id FROM knowledge_page_versions WHERE knowledge_page_id IN (SELECT id FROM browser_knowledge_pages)
  );
DELETE FROM knowledge_page_versions
WHERE tenant_id = '$tenant_id' AND knowledge_page_id IN (SELECT id FROM browser_knowledge_pages);
ALTER TABLE knowledge_page_versions ENABLE TRIGGER immutable_knowledge_page_versions;
ALTER TABLE knowledge_citations ENABLE TRIGGER immutable_knowledge_citations;
ALTER TABLE knowledge_links ENABLE TRIGGER immutable_knowledge_links;
DELETE FROM projection_deliveries
WHERE outbox_event_id IN (
  SELECT id FROM outbox_events
  WHERE tenant_id = '$tenant_id'
    AND payload ->> 'staged_fact_id' IN (SELECT id FROM browser_evidence_facts)
);
DELETE FROM outbox_events
WHERE tenant_id = '$tenant_id'
  AND payload ->> 'staged_fact_id' IN (SELECT id FROM browser_evidence_facts);
DELETE FROM fact_provenance_links
WHERE tenant_id = '$tenant_id' AND staged_fact_id IN (SELECT id FROM browser_evidence_facts);
DELETE FROM evidence_claims
WHERE tenant_id = '$tenant_id'
  AND id IN (SELECT resource_id FROM browser_evidence_facts WHERE resource_id IS NOT NULL);
DELETE FROM staged_facts
WHERE tenant_id = '$tenant_id' AND id IN (SELECT id FROM browser_evidence_facts);
DELETE FROM extraction_runs
WHERE tenant_id = '$tenant_id' AND model_provider = 'browser-acceptance-evidence';
DELETE FROM source_versions
WHERE tenant_id = '$tenant_id' AND source_asset_id IN (
  SELECT id FROM source_assets WHERE data_source_id IN (
    SELECT id FROM data_sources WHERE tenant_id = '$tenant_id' AND name LIKE 'Browser evidence e2e-%'
  )
);
DELETE FROM source_assets
WHERE tenant_id = '$tenant_id' AND data_source_id IN (
  SELECT id FROM data_sources WHERE tenant_id = '$tenant_id' AND name LIKE 'Browser evidence e2e-%'
);
DELETE FROM source_documents
WHERE tenant_id = '$tenant_id' AND title LIKE 'Browser evidence e2e-%';
DELETE FROM data_sources
WHERE tenant_id = '$tenant_id' AND name LIKE 'Browser evidence e2e-%';
DELETE FROM knowledge_pages
WHERE tenant_id = '$tenant_id' AND id IN (SELECT id FROM browser_knowledge_pages);
CREATE TEMP TABLE browser_quality_issues (id varchar(36) PRIMARY KEY, snapshot_id varchar(36)) ON COMMIT DROP;
INSERT INTO browser_quality_issues
SELECT id, last_snapshot_id FROM data_quality_issues
WHERE tenant_id = '$tenant_id' AND active_key LIKE 'browser:e2e-%';
DELETE FROM audit_events
WHERE tenant_id = '$tenant_id'
  AND resource_type = 'data_quality_issue'
  AND resource_id IN (SELECT id FROM browser_quality_issues);
ALTER TABLE data_quality_issue_events DISABLE TRIGGER immutable_data_quality_issue_events;
DELETE FROM data_quality_issue_events
WHERE tenant_id = '$tenant_id' AND issue_id IN (SELECT id FROM browser_quality_issues);
ALTER TABLE data_quality_issue_events ENABLE TRIGGER immutable_data_quality_issue_events;
DELETE FROM data_quality_issues
WHERE tenant_id = '$tenant_id' AND id IN (SELECT id FROM browser_quality_issues);
DELETE FROM data_quality_snapshots
WHERE tenant_id = '$tenant_id'
  AND id IN (SELECT snapshot_id FROM browser_quality_issues)
  AND definitions_version LIKE 'browser-e2e-%';
CREATE TEMP TABLE browser_publication_facts (id varchar(36) PRIMARY KEY, resource_id varchar(36)) ON COMMIT DROP;
INSERT INTO browser_publication_facts
SELECT id, published_resource_id FROM staged_facts
WHERE tenant_id = '$tenant_id' AND fact_key LIKE 'browser-publication-e2e-%';
CREATE TEMP TABLE browser_publication_batches (id varchar(36) PRIMARY KEY) ON COMMIT DROP;
INSERT INTO browser_publication_batches
SELECT DISTINCT publication_batch_id FROM governance_publication_batch_items
WHERE tenant_id = '$tenant_id' AND staged_fact_id IN (SELECT id FROM browser_publication_facts);
DELETE FROM projection_deliveries
WHERE outbox_event_id IN (
  SELECT id FROM outbox_events
  WHERE tenant_id = '$tenant_id'
    AND payload ->> 'staged_fact_id' IN (SELECT id FROM browser_publication_facts)
);
DELETE FROM outbox_events
WHERE tenant_id = '$tenant_id'
  AND payload ->> 'staged_fact_id' IN (SELECT id FROM browser_publication_facts);
DELETE FROM audit_events
WHERE tenant_id = '$tenant_id'
  AND resource_type = 'governance_publication_batch'
  AND resource_id IN (SELECT id FROM browser_publication_batches);
ALTER TABLE fact_withdrawal_tombstones DISABLE TRIGGER immutable_fact_withdrawal_tombstones;
DELETE FROM fact_withdrawal_tombstones
WHERE tenant_id = '$tenant_id' AND staged_fact_id IN (SELECT id FROM browser_publication_facts);
ALTER TABLE fact_withdrawal_tombstones ENABLE TRIGGER immutable_fact_withdrawal_tombstones;
DELETE FROM governance_publication_batch_items
WHERE tenant_id = '$tenant_id' AND staged_fact_id IN (SELECT id FROM browser_publication_facts);
DELETE FROM governance_publication_batches
WHERE tenant_id = '$tenant_id' AND id IN (SELECT id FROM browser_publication_batches);
DELETE FROM fact_provenance_links
WHERE tenant_id = '$tenant_id' AND staged_fact_id IN (SELECT id FROM browser_publication_facts);
DELETE FROM evidence_claims
WHERE tenant_id = '$tenant_id' AND id IN (
  SELECT resource_id FROM browser_publication_facts WHERE resource_id IS NOT NULL
);
DELETE FROM review_tasks
WHERE tenant_id = '$tenant_id' AND staged_fact_id IN (SELECT id FROM browser_publication_facts);
DELETE FROM staged_facts
WHERE tenant_id = '$tenant_id' AND id IN (SELECT id FROM browser_publication_facts);
DELETE FROM extraction_runs
WHERE tenant_id = '$tenant_id' AND model_provider = 'browser-acceptance';
DELETE FROM audit_events
WHERE tenant_id = '$tenant_id'
  AND resource_type = 'ingestion_run'
  AND resource_id IN (
    SELECT id FROM ingestion_runs
    WHERE tenant_id = '$tenant_id' AND data_source_id IN (
      SELECT id FROM data_sources
      WHERE tenant_id = '$tenant_id' AND name LIKE 'Browser replay e2e-%'
    )
  );
DELETE FROM ingestion_run_operations
WHERE tenant_id = '$tenant_id' AND ingestion_run_id IN (
  SELECT id FROM ingestion_runs
  WHERE tenant_id = '$tenant_id' AND data_source_id IN (
    SELECT id FROM data_sources
    WHERE tenant_id = '$tenant_id' AND name LIKE 'Browser replay e2e-%'
  )
);
DELETE FROM ingestion_findings
WHERE tenant_id = '$tenant_id' AND ingestion_run_id IN (
  SELECT id FROM ingestion_runs
  WHERE tenant_id = '$tenant_id' AND data_source_id IN (
    SELECT id FROM data_sources
    WHERE tenant_id = '$tenant_id' AND name LIKE 'Browser replay e2e-%'
  )
);
DELETE FROM ingestion_runs
WHERE tenant_id = '$tenant_id' AND data_source_id IN (
  SELECT id FROM data_sources
  WHERE tenant_id = '$tenant_id' AND name LIKE 'Browser replay e2e-%'
);
DELETE FROM source_version_operations
WHERE tenant_id = '$tenant_id' AND source_version_id IN (
  SELECT sv.id FROM source_versions sv
  JOIN source_assets sa ON sa.id = sv.source_asset_id
  WHERE sa.data_source_id IN (
    SELECT id FROM data_sources
    WHERE tenant_id = '$tenant_id' AND name LIKE 'Browser replay e2e-%'
  )
);
DELETE FROM audit_events
WHERE tenant_id = '$tenant_id'
  AND resource_type = 'source_version'
  AND resource_id IN (
    SELECT sv.id FROM source_versions sv
    JOIN source_assets sa ON sa.id = sv.source_asset_id
    WHERE sa.data_source_id IN (
      SELECT id FROM data_sources
      WHERE tenant_id = '$tenant_id' AND name LIKE 'Browser replay e2e-%'
    )
  );
ALTER TABLE source_version_quarantine_decisions DISABLE TRIGGER immutable_source_version_quarantine_decisions;
DELETE FROM source_version_quarantine_decisions
WHERE tenant_id = '$tenant_id' AND source_version_id IN (
  SELECT sv.id FROM source_versions sv
  JOIN source_assets sa ON sa.id = sv.source_asset_id
  WHERE sa.data_source_id IN (
    SELECT id FROM data_sources
    WHERE tenant_id = '$tenant_id' AND name LIKE 'Browser replay e2e-%'
  )
);
ALTER TABLE source_version_quarantine_decisions ENABLE TRIGGER immutable_source_version_quarantine_decisions;
DELETE FROM source_versions
WHERE tenant_id = '$tenant_id' AND source_asset_id IN (
  SELECT id FROM source_assets WHERE data_source_id IN (
    SELECT id FROM data_sources
    WHERE tenant_id = '$tenant_id' AND name LIKE 'Browser replay e2e-%'
  )
);
DELETE FROM source_assets
WHERE tenant_id = '$tenant_id' AND data_source_id IN (
  SELECT id FROM data_sources
  WHERE tenant_id = '$tenant_id' AND name LIKE 'Browser replay e2e-%'
);
DELETE FROM data_sources
WHERE tenant_id = '$tenant_id' AND name LIKE 'Browser replay e2e-%';
COMMIT;
SQL
  docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -At -v ON_ERROR_STOP=1 \
    -c "SELECT id FROM entities WHERE tenant_id = '$tenant_id' AND attributes ->> 'acceptance_fixture' = 'true' ORDER BY id" \
    > "$fixture_ids_path"
  docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -v ON_ERROR_STOP=1 >/dev/null <<SQL
BEGIN;
CREATE TEMP TABLE browser_fixture_entities (id varchar(36) PRIMARY KEY) ON COMMIT DROP;
INSERT INTO browser_fixture_entities
SELECT id FROM entities
WHERE tenant_id = '$tenant_id' AND attributes ->> 'acceptance_fixture' = 'true';
CREATE TEMP TABLE browser_fixture_comparison_sets (id varchar(36) PRIMARY KEY) ON COMMIT DROP;
INSERT INTO browser_fixture_comparison_sets
SELECT DISTINCT comparison_set_id FROM comparison_set_members
WHERE tenant_id = '$tenant_id'
  AND entity_id IN (SELECT id FROM browser_fixture_entities);
ALTER TABLE workspace_export_events DISABLE TRIGGER immutable_workspace_export_events;
DELETE FROM workspace_export_events
WHERE tenant_id = '$tenant_id'
  AND comparison_set_id IN (SELECT id FROM browser_fixture_comparison_sets);
ALTER TABLE workspace_export_events ENABLE TRIGGER immutable_workspace_export_events;
DELETE FROM audit_events
WHERE tenant_id = '$tenant_id'
  AND resource_type = 'comparison_set'
  AND resource_id IN (SELECT id FROM browser_fixture_comparison_sets);
DELETE FROM comparison_set_members
WHERE tenant_id = '$tenant_id'
  AND comparison_set_id IN (SELECT id FROM browser_fixture_comparison_sets);
ALTER TABLE comparison_set_versions DISABLE TRIGGER immutable_comparison_set_versions;
DELETE FROM comparison_set_versions
WHERE tenant_id = '$tenant_id'
  AND comparison_set_id IN (SELECT id FROM browser_fixture_comparison_sets);
ALTER TABLE comparison_set_versions ENABLE TRIGGER immutable_comparison_set_versions;
DELETE FROM comparison_sets
WHERE tenant_id = '$tenant_id'
  AND id IN (SELECT id FROM browser_fixture_comparison_sets);
DELETE FROM regulatory_events
WHERE tenant_id = '$tenant_id'
  AND (
    subject_entity_id IN (SELECT id FROM browser_fixture_entities)
    OR indication_entity_id IN (SELECT id FROM browser_fixture_entities)
    OR organization_entity_id IN (SELECT id FROM browser_fixture_entities)
  );
DELETE FROM epidemiology_observations
WHERE tenant_id = '$tenant_id'
  AND (
    disease_entity_id IN (SELECT id FROM browser_fixture_entities)
    OR publisher_entity_id IN (SELECT id FROM browser_fixture_entities)
  );
DELETE FROM patient_population_entity_links
WHERE tenant_id = '$tenant_id'
  AND (
    entity_id IN (SELECT id FROM browser_fixture_entities)
    OR patient_population_id IN (
      SELECT id FROM patient_populations
      WHERE tenant_id = '$tenant_id' AND attributes ->> 'acceptance_fixture' = 'true'
    )
  );
DELETE FROM patient_populations
WHERE tenant_id = '$tenant_id' AND attributes ->> 'acceptance_fixture' = 'true';
DELETE FROM deal_rights
WHERE tenant_id = '$tenant_id' AND deal_id IN (
  SELECT id FROM deal_profiles
  WHERE tenant_id = '$tenant_id' AND entity_id IN (SELECT id FROM browser_fixture_entities)
);
DELETE FROM deal_asset_associations
WHERE tenant_id = '$tenant_id' AND deal_id IN (
  SELECT id FROM deal_profiles
  WHERE tenant_id = '$tenant_id' AND entity_id IN (SELECT id FROM browser_fixture_entities)
);
DELETE FROM deal_party_associations
WHERE tenant_id = '$tenant_id' AND deal_id IN (
  SELECT id FROM deal_profiles
  WHERE tenant_id = '$tenant_id' AND entity_id IN (SELECT id FROM browser_fixture_entities)
);
DELETE FROM deal_profiles
WHERE tenant_id = '$tenant_id' AND entity_id IN (SELECT id FROM browser_fixture_entities);
ALTER TABLE development_program_organizations DISABLE TRIGGER immutable_development_program_organizations;
DELETE FROM development_program_organizations
WHERE tenant_id = '$tenant_id'
  AND program_id IN (
    SELECT id FROM development_programs
    WHERE tenant_id = '$tenant_id'
      AND (
        drug_entity_id IN (SELECT id FROM browser_fixture_entities)
        OR target_entity_id IN (SELECT id FROM browser_fixture_entities)
        OR disease_entity_id IN (SELECT id FROM browser_fixture_entities)
        OR organization_entity_id IN (SELECT id FROM browser_fixture_entities)
      )
  );
ALTER TABLE development_program_organizations ENABLE TRIGGER immutable_development_program_organizations;
ALTER TABLE development_program_targets DISABLE TRIGGER immutable_development_program_targets;
DELETE FROM development_program_targets
WHERE tenant_id = '$tenant_id'
  AND program_id IN (
    SELECT id FROM development_programs
    WHERE tenant_id = '$tenant_id'
      AND (
        drug_entity_id IN (SELECT id FROM browser_fixture_entities)
        OR target_entity_id IN (SELECT id FROM browser_fixture_entities)
        OR disease_entity_id IN (SELECT id FROM browser_fixture_entities)
        OR organization_entity_id IN (SELECT id FROM browser_fixture_entities)
      )
  );
ALTER TABLE development_program_targets ENABLE TRIGGER immutable_development_program_targets;
DELETE FROM development_programs
WHERE tenant_id = '$tenant_id'
  AND (
    drug_entity_id IN (SELECT id FROM browser_fixture_entities)
    OR target_entity_id IN (SELECT id FROM browser_fixture_entities)
    OR disease_entity_id IN (SELECT id FROM browser_fixture_entities)
    OR organization_entity_id IN (SELECT id FROM browser_fixture_entities)
  );
DELETE FROM clinical_trial_result_disclosures
WHERE tenant_id = '$tenant_id'
  AND trial_id IN (
    SELECT id FROM clinical_trial_profiles
    WHERE tenant_id = '$tenant_id' AND entity_id IN (SELECT id FROM browser_fixture_entities)
  );
DELETE FROM clinical_trial_entity_roles
WHERE tenant_id = '$tenant_id'
  AND (
    entity_id IN (SELECT id FROM browser_fixture_entities)
    OR trial_id IN (
      SELECT id FROM clinical_trial_profiles
      WHERE tenant_id = '$tenant_id' AND entity_id IN (SELECT id FROM browser_fixture_entities)
    )
  );
DELETE FROM clinical_trial_profiles
WHERE tenant_id = '$tenant_id' AND entity_id IN (SELECT id FROM browser_fixture_entities);
DELETE FROM patent_families
WHERE tenant_id = '$tenant_id' AND entity_id IN (SELECT id FROM browser_fixture_entities);
DELETE FROM activity_measurements
WHERE tenant_id = '$tenant_id'
  AND (
    compound_entity_id IN (SELECT id FROM browser_fixture_entities)
    OR target_entity_id IN (SELECT id FROM browser_fixture_entities)
    OR source_activity_id LIKE 'E2E-e2e-%'
  );
DELETE FROM assays
WHERE tenant_id = '$tenant_id'
  AND (
    target_entity_id IN (SELECT id FROM browser_fixture_entities)
    OR source_assay_id LIKE 'E2E-e2e-%'
  );
DELETE FROM compound_structures
WHERE tenant_id = '$tenant_id' AND entity_id IN (SELECT id FROM browser_fixture_entities);
DELETE FROM news_events
WHERE tenant_id = '$tenant_id' AND event_identifier LIKE 'E2E-e2e-%';
DELETE FROM projection_deliveries
WHERE outbox_event_id IN (
  SELECT id FROM outbox_events
  WHERE tenant_id = '$tenant_id' AND aggregate_type = 'entity'
    AND aggregate_id IN (SELECT id FROM browser_fixture_entities)
);
DELETE FROM outbox_events
WHERE tenant_id = '$tenant_id' AND aggregate_type = 'entity'
  AND aggregate_id IN (SELECT id FROM browser_fixture_entities);
ALTER TABLE entity_resolution_decisions DISABLE TRIGGER immutable_entity_resolution_decisions;
DELETE FROM entity_resolution_decisions
WHERE tenant_id = '$tenant_id' AND resolution_case_id IN (
  SELECT id FROM entity_resolution_cases
  WHERE tenant_id = '$tenant_id'
    AND (
      source_entity_id IN (SELECT id FROM browser_fixture_entities)
      OR candidate_entity_id IN (SELECT id FROM browser_fixture_entities)
    )
);
ALTER TABLE entity_resolution_decisions ENABLE TRIGGER immutable_entity_resolution_decisions;
DELETE FROM entity_canonical_links
WHERE tenant_id = '$tenant_id'
  AND (
    alias_entity_id IN (SELECT id FROM browser_fixture_entities)
    OR canonical_entity_id IN (SELECT id FROM browser_fixture_entities)
  );
DELETE FROM entity_resolution_cases
WHERE tenant_id = '$tenant_id'
  AND (
    source_entity_id IN (SELECT id FROM browser_fixture_entities)
    OR candidate_entity_id IN (SELECT id FROM browser_fixture_entities)
  );
DELETE FROM target_profiles
WHERE tenant_id = '$tenant_id' AND entity_id IN (SELECT id FROM browser_fixture_entities);
DELETE FROM entity_ontology_mappings
WHERE tenant_id = '$tenant_id' AND entity_id IN (SELECT id FROM browser_fixture_entities);
DELETE FROM entity_identifiers
WHERE tenant_id = '$tenant_id' AND entity_id IN (SELECT id FROM browser_fixture_entities);
DELETE FROM source_documents
WHERE tenant_id = '$tenant_id' AND title LIKE 'Browser publication e2e-%';
DELETE FROM entity_aliases
WHERE tenant_id = '$tenant_id' AND entity_id IN (SELECT id FROM browser_fixture_entities);
DELETE FROM entities
WHERE tenant_id = '$tenant_id' AND id IN (SELECT id FROM browser_fixture_entities);
COMMIT;
SQL
  while IFS= read -r fixture_id; do
    [[ -n "$fixture_id" ]] || continue
    [[ "$fixture_id" =~ ^[0-9a-f-]{36}$ ]] || {
      echo "Database returned an unsafe browser fixture ID" >&2
      return 1
    }
    docker compose exec -T opensearch curl --silent --show-error --request DELETE \
      "http://127.0.0.1:9200/$opensearch_index_prefix-entities-write/_doc/$tenant_id:$fixture_id?routing=$tenant_id&refresh=true" \
      > "$output_dir/opensearch-delete-$fixture_id.json"
    python3 - "$output_dir/opensearch-delete-$fixture_id.json" <<'PY'
import json
import sys
from pathlib import Path

result = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8")).get("result")
if result not in {"deleted", "not_found"}:
    raise SystemExit(f"unexpected OpenSearch fixture deletion result: {result}")
PY
  done < "$fixture_ids_path"
  if [[ -f "$projection_ids_path" ]]; then
    while IFS='|' read -r projection_kind projection_id; do
      [[ -n "$projection_kind" && -n "$projection_id" ]] || continue
      case "$projection_kind" in
        evidence) projection_index="$opensearch_index_prefix-evidence-write" ;;
        knowledge) projection_index="$opensearch_index_prefix-knowledge-write" ;;
        *) echo "Database returned an unsafe browser projection kind" >&2; return 1 ;;
      esac
      [[ "$projection_id" =~ ^[0-9a-f-]{36}:(claim:)?[0-9a-f-]{36}$ ]] || {
        echo "Database returned an unsafe browser projection ID" >&2
        return 1
      }
      projection_delete_path="$output_dir/opensearch-delete-projection-${projection_kind}-$(printf '%s' "$projection_id" | tr ':' '-').json"
      docker compose exec -T opensearch curl --silent --show-error --request DELETE \
        "http://127.0.0.1:9200/$projection_index/_doc/$projection_id?routing=$tenant_id&refresh=true" \
        > "$projection_delete_path"
      python3 - "$projection_delete_path" <<'PY'
import json
import sys
from pathlib import Path

result = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8")).get("result")
if result not in {"deleted", "not_found"}:
    raise SystemExit(f"unexpected OpenSearch projection deletion result: {result}")
PY
    done < "$projection_ids_path"
  fi
  for project in "${browser_projects[@]}"; do
    rmdir "$fixture_source_root/$project" 2>/dev/null || true
  done
  rmdir "$fixture_source_root" 2>/dev/null || true
}
cleanup_worker_was_running=false
cleanup_worker_stopped=false
pause_worker_for_cleanup() {
  [[ "$cleanup_worker_stopped" == true ]] && return 0
  local worker_container_id
  worker_container_id=$(docker compose ps --status running -q worker 2>/dev/null || true)
  if [[ -n "$worker_container_id" ]]; then
    docker compose stop worker >/dev/null
    cleanup_worker_was_running=true
  fi
  cleanup_worker_stopped=true
}
resume_worker_after_cleanup() {
  [[ "$cleanup_worker_stopped" == true ]] || return 0
  if [[ "$cleanup_worker_was_running" == true ]]; then
    docker compose start worker >/dev/null
  fi
  cleanup_worker_was_running=false
  cleanup_worker_stopped=false
}
wait_for_worker_healthy() {
  local worker_container_id
  worker_container_id=$(docker compose ps -q worker)
  wait_for_browser_container_healthy "$worker_container_id" worker 60
}
restore_runtime_projection() {
  # The acceptance build moves the shared aliases to browser-scoped indices. Rebuild
  # through a one-off worker while the long-running worker is stopped so its startup
  # guard never observes the temporary aliases and enters a crash loop.
  docker compose run --rm --no-deps worker pharma-search rebuild --build-id "runtime-$run_id" >/dev/null
  SEARCH_ALLOW_NON_AUTHORITATIVE_PROJECTION=false docker compose up -d --no-deps --force-recreate worker >/dev/null
  wait_for_worker_healthy
  wait_for_browser_container_healthy "$api_container_id" api 30
  cleanup_worker_was_running=false
  cleanup_worker_stopped=false
}
cleanup_output() {
  if [[ $keep_browser_output == false && -d "$output_dir" && "$output_dir" == /tmp/pharma-browser-acceptance-* ]]; then
    find "$output_dir" -mindepth 1 -delete
    rmdir "$output_dir"
  elif [[ $keep_browser_output == true && -d "$output_dir" ]]; then
    echo "Preserved browser artifacts: $output_dir" >&2
  fi
}
cleanup_on_exit() {
  if [[ "$cleanup_completed" == true ]]; then
    cleanup_output
    return 0
  fi
  set +e
  pause_worker_for_cleanup
  cleanup_fixtures
  cleanup_account
  if restore_runtime_projection; then
    resume_worker_after_cleanup
    cleanup_completed=true
  else
    echo "Failed to restore the authoritative runtime search projection after browser cleanup" >&2
  fi
  cleanup_output
}
trap cleanup_on_exit EXIT

if [[ "$recover_interrupted_run" == true ]]; then
  pause_worker_for_cleanup
  cleanup_fixtures
  cleanup_account
  restore_runtime_projection
  resume_worker_after_cleanup
  cleanup_completed=true
  remaining_accounts=$(docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -At -v ON_ERROR_STOP=1 \
    -c "SELECT count(*) FROM users WHERE normalized_email LIKE 'e2e-%@example.test'")
  remaining_fixtures=$(docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -At -v ON_ERROR_STOP=1 \
    -c "SELECT (SELECT count(*) FROM entities WHERE tenant_id = '$tenant_id' AND attributes ->> 'acceptance_fixture' = 'true') + (SELECT count(*) FROM patient_populations WHERE tenant_id = '$tenant_id' AND attributes ->> 'acceptance_fixture' = 'true')")
  if [[ "$remaining_accounts" != "0" || "$remaining_fixtures" != "0" ]]; then
    echo "Interrupted browser fixture recovery did not remove all temporary state" >&2
    exit 1
  fi
  printf '%s\n' "BROWSER_ACCEPTANCE_RECOVERY status=passed temporary_accounts_after=0 temporary_entities_after=0"
  exit 0
fi

stale_accounts=$(
  docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -At -v ON_ERROR_STOP=1 \
    -c "SELECT count(*) FROM users WHERE normalized_email LIKE 'e2e-%@example.test'"
)
if [[ "$stale_accounts" != "0" ]]; then
  echo "Refusing to run with stale e2e accounts: $stale_accounts" >&2
  exit 1
fi
stale_fixtures=$(
  docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -At -v ON_ERROR_STOP=1 \
    -c "SELECT (SELECT count(*) FROM entities WHERE tenant_id = '$tenant_id' AND attributes ->> 'acceptance_fixture' = 'true') + (SELECT count(*) FROM patient_populations WHERE tenant_id = '$tenant_id' AND attributes ->> 'acceptance_fixture' = 'true')"
)
if [[ "$stale_fixtures" != "0" ]]; then
  echo "Refusing to run with stale browser fixtures: $stale_fixtures" >&2
  exit 1
fi
stale_ingestion_fixtures=$(
  docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -At -v ON_ERROR_STOP=1 \
    -c "SELECT count(*) FROM data_sources WHERE tenant_id = '$tenant_id' AND name LIKE 'Browser replay e2e-%'"
)
if [[ "$stale_ingestion_fixtures" != "0" ]]; then
  echo "Refusing to run with stale ingestion fixtures: $stale_ingestion_fixtures" >&2
  exit 1
fi
stale_publication_fixtures=$(
  docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -At -v ON_ERROR_STOP=1 \
    -c "SELECT count(*) FROM staged_facts WHERE tenant_id = '$tenant_id' AND fact_key LIKE 'browser-publication-e2e-%'"
)
if [[ "$stale_publication_fixtures" != "0" ]]; then
  echo "Refusing to run with stale publication fixtures: $stale_publication_fixtures" >&2
  exit 1
fi
stale_governed_fixtures=$(
  docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -At -v ON_ERROR_STOP=1 \
    -c "SELECT (SELECT count(*) FROM knowledge_pages WHERE tenant_id = '$tenant_id' AND page_key LIKE 'browser/e2e-%') + (SELECT count(*) FROM evidence_claims WHERE tenant_id = '$tenant_id' AND source_document_id IN (SELECT id FROM source_documents WHERE tenant_id = '$tenant_id' AND title LIKE 'Browser evidence e2e-%')) + (SELECT count(*) FROM data_sources WHERE tenant_id = '$tenant_id' AND name LIKE 'Browser evidence e2e-%')"
)
if [[ "$stale_governed_fixtures" != "0" ]]; then
  echo "Refusing to run with stale governed fixtures: $stale_governed_fixtures; run --recover-interrupted-run first" >&2
  exit 1
fi
stale_quality_fixtures=$(
  docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -At -v ON_ERROR_STOP=1 \
    -c "SELECT count(*) FROM data_quality_issues WHERE tenant_id = '$tenant_id' AND active_key LIKE 'browser:e2e-%'"
)
if [[ "$stale_quality_fixtures" != "0" ]]; then
  echo "Refusing to run with stale quality fixtures: $stale_quality_fixtures" >&2
  exit 1
fi

browser_user_id=""
declare -A project_user_ids
declare -A search_target_ids search_company_ids
for project in "${browser_projects[@]}"; do
  project_email="$email_prefix-$project@example.test"
  docker compose run --rm --no-deps migrate pharma-bootstrap \
    --tenant-slug "$tenant_slug" \
    --tenant-name "Browser Acceptance" \
    --skip-api-key \
    --admin-email "$project_email" \
    --admin-password "$password" \
    --admin-name "Browser Acceptance" >/dev/null
  project_user_id=$(
    docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -At -v ON_ERROR_STOP=1 \
      -c "SELECT id FROM users WHERE normalized_email = '$project_email'"
  )
  [[ "$project_user_id" =~ ^[0-9a-f-]{36}$ ]] || {
    echo "Browser acceptance user was not created for project: $project" >&2
    exit 1
  }
  if [[ "$project" == desktop-1440 ]]; then
    browser_user_id="$project_user_id"
  fi
  project_user_ids[$project]=$project_user_id
  search_target_ids[$project]=$(python3 -c 'import uuid; print(uuid.uuid4())')
  search_company_ids[$project]=$(python3 -c 'import uuid; print(uuid.uuid4())')
  project_fixture_key="$fixture_key-$project"
  docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -v ON_ERROR_STOP=1 \
    -v tenant_id="$tenant_id" -v target_id="${search_target_ids[$project]}" \
    -v company_id="${search_company_ids[$project]}" -v fixture_key="$project_fixture_key" \
    -v target_name="Browser acceptance target $project_fixture_key" \
    -v company_name="Browser acceptance company $project_fixture_key" \
    < scripts/browser_fixtures/research_entities.sql >/dev/null
done
[[ "$browser_user_id" =~ ^[0-9a-f-]{36}$ ]] || {
  echo "Browser acceptance policy owner was not created" >&2
  exit 1
}
permission_email="$email_prefix-viewer@example.test"
permission_password="$(openssl rand -hex 24)Aa1!"
permission_user_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
permission_password_hash=$(
  docker compose exec -T api python3 -c \
    'import sys; from pharma_intel.security import hash_password; print(hash_password(sys.argv[1]))' \
    "$permission_password" | tr -d '\r'
)
[[ "$permission_password_hash" =~ ^\$argon2 ]] || {
  echo "Browser acceptance viewer password hash was not created" >&2
  exit 1
}
docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -v ON_ERROR_STOP=1 \
  -v tenant_id="$tenant_id" -v permission_user_id="$permission_user_id" \
  -v permission_email="$permission_email" -v permission_password_hash="$permission_password_hash" \
  >/dev/null <<'SQL'
INSERT INTO users (
  id, home_tenant_id, email, normalized_email, display_name, password_hash,
  active, token_version, created_at, updated_at
) VALUES (
  :'permission_user_id', :'tenant_id', :'permission_email', lower(:'permission_email'),
  'Browser Permission Viewer', :'permission_password_hash', true, 1, now(), now()
);
INSERT INTO organization_memberships (tenant_id, user_id, role, active, token_version, created_at, updated_at)
VALUES (:'tenant_id', :'permission_user_id', 'VIEWER', true, 1, now(), now());
SQL
policy_snapshot=$(
  docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -At -v ON_ERROR_STOP=1 \
    -c "SELECT row_to_json(policy)::text FROM workspace_export_policies AS policy WHERE tenant_id = '$tenant_id'"
)
policy_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -v ON_ERROR_STOP=1 \
  -v policy_id="$policy_id" -v tenant_id="$tenant_id" -v user_id="$browser_user_id" >/dev/null <<'SQL'
INSERT INTO workspace_export_policies (
  id, tenant_id, policy_version, enabled, allowed_formats, allowed_fields,
  max_records_per_export, attribution, configured_by_user_id, created_at, updated_at
) VALUES (
  :'policy_id', :'tenant_id', 'browser-domain-export-v1', true, '["json"]'::json,
  '["id","entity_type","name","entities.id","entities.entity_type","entities.name","entities.description","entities.external_ids","entities.review_status","entities.updated_at"]'::json,
  20, 'Controlled browser acceptance export', :'user_id', now(), now()
)
ON CONFLICT (tenant_id) DO UPDATE SET
  policy_version = EXCLUDED.policy_version,
  enabled = EXCLUDED.enabled,
  allowed_formats = EXCLUDED.allowed_formats,
  allowed_fields = EXCLUDED.allowed_fields,
  max_records_per_export = EXCLUDED.max_records_per_export,
  attribution = EXCLUDED.attribution,
  configured_by_user_id = EXCLUDED.configured_by_user_id,
  updated_at = now();
SQL
export_policy_installed=true

regulatory_subject_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
regulatory_negative_subject_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
regulatory_subject_structure_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
target_assay_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
target_activity_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
regulatory_indication_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
regulatory_company_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
regulatory_event_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
regulatory_negative_event_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
pipeline_target_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
pipeline_combination_target_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
pipeline_target_combination_key=$(python3 -c 'import sys; print("|".join(sorted(sys.argv[1:])))' "$pipeline_target_id" "$pipeline_combination_target_id")
pipeline_program_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
pipeline_drug_b_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
pipeline_drug_c_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
pipeline_company_b_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
pipeline_program_b_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
pipeline_program_c_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
pipeline_program_target_a_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
pipeline_program_target_b_primary_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
pipeline_program_target_b_combination_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
pipeline_program_target_c_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
pipeline_program_org_a_originator_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
pipeline_program_org_a_collaborator_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
pipeline_program_org_b_originator_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
pipeline_program_org_b_licensee_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
pipeline_program_org_c_originator_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
trial_entity_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
trial_profile_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
trial_disclosure_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
trial_negative_entity_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
trial_negative_profile_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
trial_drug_role_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
trial_drug_role_b_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
trial_combination_drug_role_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
trial_target_role_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
trial_combination_target_role_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
trial_negative_drug_role_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
trial_negative_combination_drug_role_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
trial_negative_target_role_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
trial_negative_combination_target_role_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
patent_entity_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
patent_family_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
patent_negative_entity_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
patent_negative_family_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
news_publisher_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
news_event_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
news_negative_event_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
deal_entity_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
deal_profile_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
deal_licensor_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
deal_licensee_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
deal_asset_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
deal_decoy_asset_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
deal_right_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
epidemiology_disease_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
epidemiology_publisher_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
epidemiology_patient_population_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
epidemiology_patient_population_link_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
epidemiology_observation_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
epidemiology_comparable_observation_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
epidemiology_incompatible_publisher_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
epidemiology_incompatible_observation_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -v ON_ERROR_STOP=1 >/dev/null <<SQL
BEGIN;
INSERT INTO entities (
  id, tenant_id, entity_type, name, normalized_name, description,
  external_ids, attributes, review_status, created_at, updated_at
) VALUES
  (
    '$regulatory_subject_id', '$tenant_id', 'DRUG', 'Browser regulatory drug $fixture_key',
    'browser regulatory drug $fixture_key', 'Controlled regulatory browser acceptance fixture',
    '{"acceptance":"$fixture_key-regulatory-drug"}',
    '{"acceptance_fixture":true,"acceptance_fixture_key":"$fixture_key"}',
    'VERIFIED', now(), now()
  ),
  (
    '$regulatory_negative_subject_id', '$tenant_id', 'DRUG', 'Browser regulatory negative drug $fixture_key',
    'browser regulatory negative drug $fixture_key', 'Controlled regulatory negative acceptance fixture',
    '{"acceptance":"$fixture_key-regulatory-negative-drug"}',
    '{"acceptance_fixture":true,"acceptance_fixture_key":"$fixture_key"}',
    'VERIFIED', now(), now()
  ),
  (
    '$regulatory_indication_id', '$tenant_id', 'DISEASE', 'Browser regulatory indication $fixture_key',
    'browser regulatory indication $fixture_key', 'Controlled regulatory browser acceptance fixture',
    '{"acceptance":"$fixture_key-regulatory-indication"}',
    '{"acceptance_fixture":true,"acceptance_fixture_key":"$fixture_key"}',
    'VERIFIED', now(), now()
  ),
  (
    '$regulatory_company_id', '$tenant_id', 'ORGANIZATION', 'Browser regulatory company $fixture_key',
    'browser regulatory company $fixture_key', 'Controlled regulatory browser acceptance fixture',
    '{"acceptance":"$fixture_key-regulatory-company"}',
    '{"acceptance_fixture":true,"acceptance_fixture_key":"$fixture_key"}',
    'VERIFIED', now(), now()
  ),
  (
    '$pipeline_target_id', '$tenant_id', 'TARGET', 'Browser pipeline target $fixture_key',
    'browser pipeline target $fixture_key', 'Controlled pipeline browser acceptance fixture',
    '{"acceptance":"$fixture_key-pipeline-target"}',
    '{"acceptance_fixture":true,"acceptance_fixture_key":"$fixture_key"}',
    'VERIFIED', now(), now()
  ),
  (
    '$pipeline_combination_target_id', '$tenant_id', 'TARGET', 'Browser combination target $fixture_key',
    'browser combination target $fixture_key', 'Controlled multi-target browser acceptance fixture',
    '{"acceptance":"$fixture_key-pipeline-combination-target"}',
    '{"acceptance_fixture":true,"acceptance_fixture_key":"$fixture_key"}',
    'VERIFIED', now(), now()
  ),
  (
    '$pipeline_drug_b_id', '$tenant_id', 'DRUG', 'Browser pipeline antibody $fixture_key',
    'browser pipeline antibody $fixture_key', 'Controlled pipeline browser acceptance fixture',
    '{"acceptance":"$fixture_key-pipeline-antibody"}',
    '{"acceptance_fixture":true,"acceptance_fixture_key":"$fixture_key","english_name":"Browser Antibody $fixture_key","innovation_type":"First-in-class","modality":"Monoclonal antibody","drug_category":"Biologic"}',
    'VERIFIED', now(), now()
  ),
  (
    '$pipeline_drug_c_id', '$tenant_id', 'DRUG', 'Browser pipeline degrader $fixture_key',
    'browser pipeline degrader $fixture_key', 'Controlled pipeline browser acceptance fixture',
    '{"acceptance":"$fixture_key-pipeline-degrader"}',
    '{"acceptance_fixture":true,"acceptance_fixture_key":"$fixture_key"}',
    'VERIFIED', now(), now()
  ),
  (
    '$pipeline_company_b_id', '$tenant_id', 'ORGANIZATION', 'Browser pipeline company B $fixture_key',
    'browser pipeline company b $fixture_key', 'Controlled pipeline browser acceptance fixture',
    '{"acceptance":"$fixture_key-pipeline-company-b"}',
    '{"acceptance_fixture":true,"acceptance_fixture_key":"$fixture_key"}',
    'VERIFIED', now(), now()
  ),
  (
    '$trial_entity_id', '$tenant_id', 'CLINICAL_TRIAL', 'NCT-E2E-$fixture_key',
    'nct-e2e-$fixture_key', 'Controlled clinical trial browser acceptance fixture',
    '{"acceptance":"$fixture_key-trial"}',
    '{"acceptance_fixture":true,"acceptance_fixture_key":"$fixture_key"}',
    'VERIFIED', now(), now()
  ),
  (
    '$trial_negative_entity_id', '$tenant_id', 'CLINICAL_TRIAL', 'NCT-E2E-NEGATIVE-$fixture_key',
    'nct-e2e-negative-$fixture_key', 'Controlled clinical role negative acceptance fixture',
    '{"acceptance":"$fixture_key-trial-negative"}',
    '{"acceptance_fixture":true,"acceptance_fixture_key":"$fixture_key"}',
    'VERIFIED', now(), now()
  ),
  (
    '$patent_entity_id', '$tenant_id', 'PATENT', 'WO-E2E-$fixture_key',
    'wo-e2e-$fixture_key', 'Controlled patent browser acceptance fixture',
    '{"acceptance":"$fixture_key-patent"}',
    '{"acceptance_fixture":true,"acceptance_fixture_key":"$fixture_key"}',
    'VERIFIED', now(), now()
  ),
  (
    '$patent_negative_entity_id', '$tenant_id', 'PATENT', 'WO-E2E-NEGATIVE-$fixture_key',
    'wo-e2e-negative-$fixture_key', 'Controlled patent status negative acceptance fixture',
    '{"acceptance":"$fixture_key-patent-negative"}',
    '{"acceptance_fixture":true,"acceptance_fixture_key":"$fixture_key"}',
    'VERIFIED', now(), now()
  ),
  (
    '$news_publisher_id', '$tenant_id', 'ORGANIZATION', 'Browser publisher $fixture_key',
    'browser publisher $fixture_key', 'Controlled news browser acceptance fixture',
    '{"acceptance":"$fixture_key-news-publisher"}',
    '{"acceptance_fixture":true,"acceptance_fixture_key":"$fixture_key"}',
    'VERIFIED', now(), now()
  ),
  (
    '$deal_entity_id', '$tenant_id', 'TRANSACTION', 'Browser deal $fixture_key',
    'browser deal $fixture_key', 'Controlled deal browser acceptance fixture',
    '{"acceptance":"$fixture_key-deal"}',
    '{"acceptance_fixture":true,"acceptance_fixture_key":"$fixture_key"}',
    'VERIFIED', now(), now()
  ),
  (
    '$epidemiology_disease_id', '$tenant_id', 'DISEASE', 'Browser epidemiology disease $fixture_key',
    'browser epidemiology disease $fixture_key', 'Controlled epidemiology browser acceptance fixture',
    '{"acceptance":"$fixture_key-epidemiology-disease"}',
    '{"acceptance_fixture":true,"acceptance_fixture_key":"$fixture_key"}',
    'VERIFIED', now(), now()
  ),
  (
    '$epidemiology_publisher_id', '$tenant_id', 'ORGANIZATION', 'Browser epidemiology publisher $fixture_key',
    'browser epidemiology publisher $fixture_key', 'Controlled epidemiology browser acceptance fixture',
    '{"acceptance":"$fixture_key-epidemiology-publisher"}',
    '{"acceptance_fixture":true,"acceptance_fixture_key":"$fixture_key"}',
    'VERIFIED', now(), now()
  ),
  (
    '$epidemiology_incompatible_publisher_id', '$tenant_id', 'ORGANIZATION', 'Browser alternative epidemiology publisher $fixture_key',
    'browser alternative epidemiology publisher $fixture_key', 'Controlled incompatible trend source fixture',
    '{"acceptance":"$fixture_key-epidemiology-alternative-publisher"}',
    '{"acceptance_fixture":true,"acceptance_fixture_key":"$fixture_key"}',
    'VERIFIED', now(), now()
  );
INSERT INTO entity_aliases (
  id, tenant_id, entity_id, alias, normalized_alias, language
) VALUES (
  md5('$fixture_key-pipeline-antibody-alias')::uuid,
  '$tenant_id',
  '$pipeline_drug_b_id',
  'Browser antibody alias $fixture_key',
  'browser antibody alias $fixture_key',
  'en'
);
INSERT INTO entities (
  id, tenant_id, entity_type, name, normalized_name, description,
  external_ids, attributes, review_status, created_at, updated_at
)
SELECT
  md5('$fixture_key-pagination-' || sequence_number::text)::uuid,
  '$tenant_id',
  'DRUG',
  'Visual baseline entity ' || lpad(sequence_number::text, 3, '0'),
  'visual baseline entity ' || lpad(sequence_number::text, 3, '0'),
  'Controlled real-database pagination acceptance fixture',
  jsonb_build_object('visual', 'entity-' || lpad(sequence_number::text, 3, '0')),
  jsonb_build_object(
    'acceptance_fixture', true,
    'acceptance_fixture_key', '$fixture_key',
    'acceptance_fixture_kind', 'pagination'
  ),
  'VERIFIED',
  '2026-07-01T00:00:00Z',
  '2026-07-01T00:00:00Z'
FROM generate_series(1, 205) AS sequence_number;
INSERT INTO entity_aliases (
  id, tenant_id, entity_id, alias, normalized_alias, language
)
SELECT
  md5('$fixture_key-pagination-alias-' || entity.id)::uuid,
  '$tenant_id',
  entity.id,
  'Browser pagination $fixture_key',
  'browser pagination $fixture_key',
  'en'
FROM entities AS entity
WHERE entity.tenant_id = '$tenant_id'
  AND entity.attributes ->> 'acceptance_fixture_key' = '$fixture_key'
  AND entity.attributes ->> 'acceptance_fixture_kind' = 'pagination';
INSERT INTO outbox_events (
  id, tenant_id, aggregate_type, aggregate_id, event_type, payload,
  state, attempts, available_at, published_at, last_error, created_at
)
SELECT
  md5('$fixture_key-pagination-outbox-' || entity.id)::uuid,
  '$tenant_id',
  'entity',
  entity.id,
  'canonical.entity.upserted',
  jsonb_build_object('entity_id', entity.id, 'schema_version', 1),
  'PENDING',
  0,
  now(),
  NULL,
  NULL,
  now()
FROM entities AS entity
WHERE entity.tenant_id = '$tenant_id'
  AND (
    (
      entity.attributes ->> 'acceptance_fixture_key' = '$fixture_key'
      AND entity.attributes ->> 'acceptance_fixture_kind' = 'pagination'
    )
    OR entity.id IN (
      '$pipeline_drug_b_id',
      '$pipeline_target_id',
      '$epidemiology_disease_id',
      '$regulatory_subject_id',
      '$regulatory_indication_id',
      '$regulatory_company_id'
    )
  );
INSERT INTO clinical_trial_profiles (
  id, tenant_id, entity_id, registry, registry_id, official_title, acronym,
  initiation_type, therapy_lines, overall_status, phases, study_type, enrollment,
  interventions, conditions, sponsors, outcomes,
  locations, study_design, eligibility, arms, status_history, has_results,
  result_evaluation, results_first_posted, last_update_posted, created_at, updated_at
) VALUES (
  '$trial_profile_id', '$tenant_id', '$trial_entity_id', 'ClinicalTrials.gov',
  'NCT-E2E-$fixture_key', 'Browser clinical trial $fixture_key', 'BRIDGE-$fixture_key',
  'ist', '["first_line"]', 'RECRUITING', '["PHASE2"]', 'INTERVENTIONAL', 128,
  '[{"name":"Browser intervention $fixture_key","type":"DRUG","description":"Controlled oral intervention","arm_labels":["Cohort A"],"other_names":[]}]',
  '["Browser disease $fixture_key"]',
  '[{"name":"Browser sponsor $fixture_key","sponsor_class":"INDUSTRY"}]',
  '[{"outcome_type":"PRIMARY","measure":"Objective response rate","time_frame":"24 weeks","description":"Independent review","results":[{"group_label":"Cohort A","value":"42","unit":"%","participants":128,"lower_limit":33.1,"upper_limit":51.4,"dispersion":null}],"statistical_analyses":[{"method":"Exact binomial","p_value":"0.01","parameter_type":"response_rate","parameter_value":42,"confidence_interval_percent":95,"lower_limit":33.1,"upper_limit":51.4,"notes":null}]}]',
  '[{"facility":"Shanghai Oncology Center","city":"Shanghai","state":null,"country":"China","status":"RECRUITING"}]',
  '{"allocation":"NON_RANDOMIZED","intervention_model":"SINGLE_GROUP","intervention_model_description":"Controlled single-arm phase 2 cohort","masking":"NONE","masking_description":null,"observational_model":null,"primary_purpose":"TREATMENT","time_perspective":null,"who_masked":[]}',
  '{"criteria":"Adults with confirmed browser disease","minimum_age":"18 Years","maximum_age":"80 Years","sex":"ALL","healthy_volunteers":false,"gender_based":false,"sampling_method":null}',
  '[{"label":"Cohort A","type":"EXPERIMENTAL","description":"Controlled treatment cohort","intervention_names":["Browser intervention $fixture_key"]}]',
  '[{"status":"NOT_YET_RECRUITING","effective_at":"2026-01-01T00:00:00Z","reason":"Initial registration","source_document_id":null},{"status":"RECRUITING","effective_at":"2026-02-01T00:00:00Z","reason":"First site opened","source_document_id":null}]',
  true, 'positive',
  '2026-07-20T00:00:00Z', '2026-07-21T00:00:00Z', now(), now()
);
INSERT INTO clinical_trial_profiles (
  id, tenant_id, entity_id, registry, registry_id, official_title, acronym,
  initiation_type, therapy_lines, overall_status, phases, study_type, enrollment,
  interventions, conditions, sponsors, outcomes,
  locations, study_design, eligibility, arms, status_history, has_results,
  result_evaluation, results_first_posted, last_update_posted, created_at, updated_at
)
SELECT
  '$trial_negative_profile_id', tenant_id, '$trial_negative_entity_id', registry,
  'NCT-E2E-NEGATIVE-$fixture_key', 'Browser clinical role negative $fixture_key',
  'BRIDGE-NEGATIVE-$fixture_key', initiation_type, therapy_lines, overall_status,
  phases, study_type, enrollment, interventions, conditions, sponsors, outcomes,
  locations, study_design, eligibility, arms, status_history, has_results,
  result_evaluation, results_first_posted, last_update_posted, now(), now()
FROM clinical_trial_profiles
WHERE tenant_id = '$tenant_id' AND id = '$trial_profile_id';
INSERT INTO clinical_trial_result_disclosures (
  id, tenant_id, trial_id, disclosure_key, version, disclosure_type,
  external_id, title, disclosed_at, conference_name, is_key_result,
  result_evaluation, source_locator, source_quote, source_document_id,
  created_at, updated_at
) VALUES (
  '$trial_disclosure_id', '$tenant_id', '$trial_profile_id',
  'browser-e2e-$fixture_key', 1, 'conference_abstract',
  'PMID:12345678', 'Browser key clinical result',
  '2026-07-20T00:00:00Z', 'ASCO 2026', true, 'positive',
  'https://example.test/browser/$fixture_key/clinical-result',
  'Controlled key result for browser acceptance.', NULL, now(), now()
);
INSERT INTO clinical_trial_entity_roles (
  id, tenant_id, trial_id, entity_id, role, created_at, updated_at
) VALUES (
  '$trial_drug_role_id', '$tenant_id', '$trial_profile_id', '$regulatory_subject_id',
  'investigational_drug', now(), now()
), (
  '$trial_drug_role_b_id', '$tenant_id', '$trial_profile_id', '$pipeline_drug_b_id',
  'investigational_drug', now(), now()
), (
  '$trial_combination_drug_role_id', '$tenant_id', '$trial_profile_id', '$pipeline_drug_b_id',
  'combination_drug', now(), now()
), (
  '$trial_target_role_id', '$tenant_id', '$trial_profile_id', '$pipeline_target_id',
  'investigational_target', now(), now()
), (
  '$trial_combination_target_role_id', '$tenant_id', '$trial_profile_id', '$pipeline_combination_target_id',
  'combination_target', now(), now()
), (
  '$trial_negative_drug_role_id', '$tenant_id', '$trial_negative_profile_id', '$regulatory_subject_id',
  'combination_drug', now(), now()
), (
  '$trial_negative_combination_drug_role_id', '$tenant_id', '$trial_negative_profile_id', '$pipeline_drug_b_id',
  'investigational_drug', now(), now()
), (
  '$trial_negative_target_role_id', '$tenant_id', '$trial_negative_profile_id', '$pipeline_target_id',
  'combination_target', now(), now()
), (
  '$trial_negative_combination_target_role_id', '$tenant_id', '$trial_negative_profile_id', '$pipeline_combination_target_id',
  'investigational_target', now(), now()
);
INSERT INTO patent_families (
  id, tenant_id, entity_id, family_identifier, title, priority_date, applicants,
  inventors, publications, legal_status, legal_status_at, legal_events,
  independent_claims, expiration_date, linked_entity_ids, created_at, updated_at
) VALUES (
  '$patent_family_id', '$tenant_id', '$patent_entity_id', 'WO-E2E-$fixture_key',
  'Browser patent family $fixture_key', '2024-01-10T00:00:00Z',
  '["Browser applicant $fixture_key"]', '[]',
  '[{"publication_number":"WO-E2E-$fixture_key","jurisdiction":"WO"}]',
  'ACTIVE', '2026-07-20T00:00:00Z',
  '[{"event_type":"grant","occurred_at":"2026-07-20T00:00:00Z","status":"ACTIVE","jurisdiction":"WO","publication_number":"WO-E2E-$fixture_key","description":"Controlled browser grant event"}]',
  '[{"claim_number":"1","claim_type":"composition","summary":"Controlled composition claim for browser acceptance","scope":"Browser target inhibitors"}]',
  '2044-01-10T00:00:00Z',
  '["$pipeline_target_id"]', now(), now()
), (
  '$patent_negative_family_id', '$tenant_id', '$patent_negative_entity_id', 'WO-E2E-NEGATIVE-$fixture_key',
  'Browser patent family $fixture_key', '2024-01-11T00:00:00Z',
  '["Browser applicant $fixture_key"]', '[]',
  '[{"publication_number":"WO-E2E-NEGATIVE-$fixture_key","jurisdiction":"WO"}]',
  'PENDING', '2026-07-21T00:00:00Z',
  '[{"event_type":"status_update","occurred_at":"2026-07-21T00:00:00Z","status":"PENDING","jurisdiction":"WO","publication_number":"WO-E2E-NEGATIVE-$fixture_key","description":"Controlled pending status negative"}]',
  '[{"claim_number":"1","claim_type":"composition","summary":"Controlled composition claim for browser acceptance","scope":"Browser target inhibitors"}]',
  '2044-01-11T00:00:00Z',
  '["$pipeline_target_id"]', now(), now()
);
INSERT INTO news_events (
  id, tenant_id, event_identifier, event_type, title, summary, published_at,
  language, publisher_entity_id, related_entity_ids, canonical_url, venue,
  details, created_at, updated_at
) VALUES (
  '$news_event_id', '$tenant_id', 'E2E-$fixture_key-NEWS', 'conference_abstract',
  'Browser news event $fixture_key', 'Controlled source-bearing news fixture',
  '2026-07-22T00:00:00Z', 'en', '$news_publisher_id', '["$pipeline_target_id"]',
  'https://example.test/browser/$fixture_key', 'ASCO 2026',
  '{"fixture":"browser acceptance"}', now(), now()
), (
  '$news_negative_event_id', '$tenant_id', 'E2E-$fixture_key-NEWS-NEGATIVE', 'conference_abstract',
  'Browser news venue negative $fixture_key', 'Controlled conference venue negative fixture',
  '2026-07-23T00:00:00Z', 'en', '$news_publisher_id', '["$pipeline_target_id"]',
  'https://example.test/browser/$fixture_key/negative', 'AACR 2026',
  '{"fixture":"browser acceptance","negative_dimension":"venue"}', now(), now()
);
INSERT INTO regulatory_events (
  id, tenant_id, subject_entity_id, agency, jurisdiction, event_identifier,
  application_number, event_type, status, title, decision_date,
  indication_entity_id, organization_entity_id, details,
  designation_type, label_change_type, label_version, label_effective_at,
  approved_population, line_of_therapy, biomarker, route_of_administration,
  dosage_form, has_boxed_warning, safety_signal_type, safety_term,
  safety_severity, safety_status, safety_identified_at, safety_confirmed_at,
  affected_population, risk_actions, source_updated_at, created_at, updated_at
) VALUES (
  '$regulatory_event_id', '$tenant_id', '$regulatory_subject_id', 'FDA', 'US',
  'E2E-$fixture_key', 'NDA-E2E-$fixture_key', 'approval', 'approved',
  'Browser regulatory event $fixture_key', '2026-02-20T00:00:00Z',
  '$regulatory_indication_id', '$regulatory_company_id', '{"fixture":"browser acceptance"}',
  'breakthrough_therapy', 'initial_label', 'USPI-E2E-1', '2026-02-21T00:00:00Z',
  'Adults with biomarker-positive disease', 'second_line', 'EGFR exon 20 insertion', 'oral',
  'tablet', true, 'adverse_event', 'Interstitial lung disease',
  'serious', 'confirmed', '2026-02-01T00:00:00Z', '2026-02-10T00:00:00Z',
  'Patients with prior lung injury', '["Monitor pulmonary symptoms"]',
  '2026-02-22T00:00:00Z', now(), now()
), (
  '$regulatory_negative_event_id', '$tenant_id', '$regulatory_negative_subject_id', 'FDA', 'US',
  'E2E-$fixture_key-NEGATIVE', 'NDA-E2E-$fixture_key-NEGATIVE', 'approval', 'approved',
  'Browser regulatory negative event $fixture_key', '2026-02-22T00:00:00Z',
  '$regulatory_indication_id', '$regulatory_company_id', '{"fixture":"browser acceptance negative"}',
  'breakthrough_therapy', 'initial_label', 'USPI-E2E-NEGATIVE', '2026-02-23T00:00:00Z',
  'Adults with biomarker-positive disease', 'second_line', 'EGFR exon 20 insertion', 'oral',
  'tablet', true, 'adverse_event', 'Interstitial lung disease',
  'serious', 'monitoring', '2026-02-02T00:00:00Z', NULL,
  'Patients with prior lung injury', '["Continue monitoring"]',
  '2026-02-24T00:00:00Z', now(), now()
);
INSERT INTO deal_profiles (
  id, tenant_id, entity_id, deal_type, status, direction,
  direction_reference_jurisdiction, announced_at, source_updated_at,
  parties, asset_entity_ids, territory, upfront_amount,
  total_potential_amount, currency, terms, created_at, updated_at
) VALUES (
  '$deal_profile_id', '$tenant_id', '$deal_entity_id', 'license', 'active', 'outbound',
  'US', '2026-01-20T00:00:00Z', '2026-03-15T00:00:00Z',
  '[]', '[]', 'global', 25000000, 500000000, 'USD',
  '{"fixture":"browser acceptance"}', now(), now()
);
INSERT INTO deal_party_associations (
  id, tenant_id, deal_id, party_entity_id, role, country_region,
  organization_type, created_at, updated_at
) VALUES
  (
    '$deal_licensor_id', '$tenant_id', '$deal_profile_id', '$regulatory_company_id',
    'licensor', 'US', 'biopharma', now(), now()
  ),
  (
    '$deal_licensee_id', '$tenant_id', '$deal_profile_id', '$pipeline_company_b_id',
    'licensee', 'China', 'biotech', now(), now()
  );
INSERT INTO deal_asset_associations (
  id, tenant_id, deal_id, asset_entity_id, development_phase_at_transaction,
  created_at, updated_at
) VALUES (
  '$deal_asset_id', '$tenant_id', '$deal_profile_id', '$regulatory_subject_id',
  'phase_1', now(), now()
), (
  '$deal_decoy_asset_id', '$tenant_id', '$deal_profile_id', '$pipeline_drug_b_id',
  'phase_3', now(), now()
);
INSERT INTO deal_rights (
  id, tenant_id, deal_id, holder_entity_id, right_type, territory,
  exclusive, scope_description, created_at, updated_at
) VALUES (
  '$deal_right_id', '$tenant_id', '$deal_profile_id', '$pipeline_company_b_id',
  'commercialization', 'Greater China', true,
  'Exclusive commercialization rights for the controlled browser asset', now(), now()
);
INSERT INTO patient_populations (
  id, tenant_id, population_key, name, description, attributes, review_status,
  created_at, updated_at
) VALUES (
  '$epidemiology_patient_population_id', '$tenant_id', 'browser-population-$fixture_key',
  'Browser epidemiology population $fixture_key',
  'Controlled browser acceptance patient population',
  '{"acceptance_fixture":true,"acceptance_fixture_key":"$fixture_key"}',
  'VERIFIED', now(), now()
);
INSERT INTO patient_population_entity_links (
  id, tenant_id, patient_population_id, entity_id, relationship
) VALUES (
  '$epidemiology_patient_population_link_id', '$tenant_id',
  '$epidemiology_patient_population_id', '$epidemiology_disease_id', 'disease'
);
INSERT INTO epidemiology_observations (
  id, tenant_id, observation_identifier, disease_entity_id, patient_population_id, measure,
  value, lower_bound, upper_bound, unit, geography, population_scope,
  age_group, sex, period_start, period_end, sample_size, methodology,
  publisher_entity_id, created_at, updated_at
) VALUES (
  '$epidemiology_observation_id', '$tenant_id', 'EPI-E2E-$fixture_key',
  '$epidemiology_disease_id', '$epidemiology_patient_population_id',
  'prevalence', 158000, 150000, 166000,
  'patients', 'China', 'adults', '18+', 'all',
  '2025-01-01T00:00:00Z', '2025-12-31T00:00:00Z', 12500,
  'Controlled browser acceptance methodology', '$epidemiology_publisher_id', now(), now()
), (
  '$epidemiology_comparable_observation_id', '$tenant_id', 'EPI-E2E-$fixture_key-2024',
  '$epidemiology_disease_id', '$epidemiology_patient_population_id',
  'prevalence', 149000, 141000, 157000,
  'patients', 'China', 'adults', '18+', 'all',
  '2024-01-01T00:00:00Z', '2024-12-31T00:00:00Z', 11900,
  'Controlled browser acceptance methodology', '$epidemiology_publisher_id', now(), now()
), (
  '$epidemiology_incompatible_observation_id', '$tenant_id', 'EPI-E2E-$fixture_key-2023-ALT',
  '$epidemiology_disease_id', '$epidemiology_patient_population_id',
  'prevalence', 141000, 132000, 150000,
  'patients', 'China', 'adults', '18+', 'all',
  '2023-01-01T00:00:00Z', '2023-12-31T00:00:00Z', 9800,
  'Incompatible claims-derived methodology', '$epidemiology_incompatible_publisher_id', now(), now()
);
INSERT INTO compound_structures (
  id, tenant_id, entity_id, canonical_smiles, isomeric_smiles, standard_inchi,
  standard_inchi_key, molecular_formula, molecular_weight, exact_mass,
  structure_version, standardization_version, fingerprint_version, created_at, updated_at
) VALUES (
  '$regulatory_subject_structure_id', '$tenant_id', '$regulatory_subject_id',
  'CC(=O)Oc1ccccc1C(=O)O', NULL,
  'InChI=1S/C9H8O4/c1-6(10)13-8-5-3-2-4-7(8)9(11)12/h2-5H,1H3,(H,11,12)',
  'BSYNRYMUTXBXSQ-UHFFFAOYSA-N', 'C9H8O4', 180.16, 180.042,
  'browser-fixture-v1', 'browser-fixture-v1', 'browser-fixture-v1', now(), now()
);
INSERT INTO assays (
  id, tenant_id, source_system, source_assay_id, target_entity_id,
  assay_type, assay_format, description, organism, cell_line, confidence_score,
  source_document_id, created_at, updated_at
) VALUES (
  '$target_assay_id', '$tenant_id', 'browser-e2e', 'E2E-$fixture_key-target-assay',
  '$pipeline_target_id', 'binding', 'biochemical', 'Controlled target SAR assay',
  'Homo sapiens', NULL, 95, NULL, now(), now()
);
INSERT INTO activity_measurements (
  id, tenant_id, source_system, source_activity_id, assay_id,
  compound_entity_id, target_entity_id, reported_type, reported_relation,
  reported_value, reported_units, standard_type, standard_relation,
  standard_value, standard_units, pchembl_value, qualifiers, validity_comment,
  created_at, updated_at
) VALUES (
  '$target_activity_id', '$tenant_id', 'browser-e2e', 'E2E-$fixture_key-target-activity',
  '$target_assay_id', '$regulatory_subject_id', '$pipeline_target_id', 'IC50', 'EQUAL',
  '10', 'nM', 'IC50', 'EQUAL', 10, 'nM', 8.0,
  '{"acceptance_fixture":true,"acceptance_fixture_key":"$fixture_key"}'::json,
  'Controlled real target activity fixture', now(), now()
);
INSERT INTO development_programs (
  id, tenant_id, drug_entity_id, target_entity_id, disease_entity_id, organization_entity_id,
  modality, mechanism_of_action, phase, status_detail, program_status, status_date, geography,
  innovation_type, therapeutic_area, drug_category,
  global_phase, china_phase, global_phase_started_at, china_phase_started_at,
  development_rights_regions, commercialization_rights_regions, program_tags,
  target_set_version, target_combination_key, organization_set_version,
  status_history, milestones, created_at, updated_at
) VALUES (
  '$pipeline_program_id', '$tenant_id', '$regulatory_subject_id', '$pipeline_target_id',
  '$regulatory_indication_id', '$regulatory_company_id', 'small molecule', 'covalent inhibitor',
  'PHASE_2', 'active', 'active', '2026-07-01T00:00:00Z', 'Global',
  'First-in-class', 'Oncology', 'Small molecule',
  'phase_2', 'phase_1', '2026-06-01T00:00:00Z', '2025-03-01T00:00:00Z',
  '["Global"]', '["Greater China"]', '["first_in_class"]', 1, '$pipeline_target_id', 1, '[]',
  '[{"milestone_type":"first_patient_in","title":"Global Phase II first patient in $fixture_key","occurred_at":"2026-06-15T00:00:00+00:00","geography":"Global"}]',
  now(), now()
),
(
  '$pipeline_program_b_id', '$tenant_id', '$pipeline_drug_b_id', '$pipeline_target_id',
  '$regulatory_indication_id', '$pipeline_company_b_id', 'antibody', 'ligand blocking antibody',
  'PHASE_3', 'active', 'active', '2026-06-10T00:00:00Z', 'China',
  'Best-in-class', 'Oncology', 'Biologic',
  'phase_3', 'phase_2', '2025-11-01T00:00:00Z', '2026-02-01T00:00:00Z',
  '["Global"]', '["China"]', '["best_in_class"]', 1, '$pipeline_target_combination_key', 1, '[]',
  '[{"milestone_type":"first_patient_in","title":"China Phase II first patient in $fixture_key","occurred_at":"2026-02-15T00:00:00+00:00","geography":"China"}]',
  now(), now()
),
(
  '$pipeline_program_c_id', '$tenant_id', '$pipeline_drug_c_id', '$pipeline_target_id',
  '$regulatory_indication_id', '$regulatory_company_id', 'PROTAC', 'targeted protein degrader',
  'PRECLINICAL', 'active', 'active', '2026-05-01T00:00:00Z', 'US',
  'Next generation', 'Oncology', 'Targeted degrader',
  'preclinical', NULL, '2026-01-10T00:00:00Z', NULL,
  '["US"]', '["US"]', '["next_generation"]', 1, '$pipeline_target_id', 1, '[]', '[]',
  now(), now()
);
INSERT INTO development_program_organizations (
  id, tenant_id, program_id, organization_set_version, organization_entity_id, role,
  country_region, organization_type, position, created_at, updated_at
) VALUES
  (
    '$pipeline_program_org_a_originator_id', '$tenant_id', '$pipeline_program_id', 1,
    '$regulatory_company_id', 'originator', 'CN', 'biopharma', 0, now(), now()
  ),
  (
    '$pipeline_program_org_a_collaborator_id', '$tenant_id', '$pipeline_program_id', 1,
    '$pipeline_company_b_id', 'collaborator', 'US', 'biotech', 1, now(), now()
  ),
  (
    '$pipeline_program_org_b_originator_id', '$tenant_id', '$pipeline_program_b_id', 1,
    '$pipeline_company_b_id', 'originator', 'US', 'biotech', 0, now(), now()
  ),
  (
    '$pipeline_program_org_b_licensee_id', '$tenant_id', '$pipeline_program_b_id', 1,
    '$regulatory_company_id', 'licensee', 'CN', 'biopharma', 1, now(), now()
  ),
  (
    '$pipeline_program_org_c_originator_id', '$tenant_id', '$pipeline_program_c_id', 1,
    '$regulatory_company_id', 'originator', 'CN', 'biopharma', 0, now(), now()
  );
INSERT INTO development_program_targets (
  id, tenant_id, program_id, target_set_version, target_entity_id, role, position,
  created_at, updated_at
) VALUES
  (
    '$pipeline_program_target_a_id', '$tenant_id', '$pipeline_program_id', 1,
    '$pipeline_target_id', 'primary', 0, now(), now()
  ),
  (
    '$pipeline_program_target_b_primary_id', '$tenant_id', '$pipeline_program_b_id', 1,
    '$pipeline_target_id', 'primary', 0, now(), now()
  ),
  (
    '$pipeline_program_target_b_combination_id', '$tenant_id', '$pipeline_program_b_id', 1,
    '$pipeline_combination_target_id', 'combination', 1, now(), now()
  ),
  (
    '$pipeline_program_target_c_id', '$tenant_id', '$pipeline_program_c_id', 1,
    '$pipeline_target_id', 'primary', 0, now(), now()
  );
COMMIT;
SQL
docker compose exec -T worker pharma-search drain --max-batches 1000 >/dev/null
docker compose exec -T opensearch curl --fail --silent --show-error --request POST \
  "http://127.0.0.1:9200/$opensearch_index_prefix-entities-write/_refresh" >/dev/null

dataset_key=$(
  docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -At -v ON_ERROR_STOP=1 \
    -c "SELECT dataset_key FROM tenant_datasets WHERE tenant_id = '$tenant_id' AND active IS TRUE ORDER BY dataset_key LIMIT 1"
)
[[ "$dataset_key" =~ ^[a-z][a-z0-9_-]{1,79}$ ]] || {
  echo "Browser acceptance requires an active governed dataset" >&2
  exit 1
}
declare -A ingestion_run_ids
declare -A quarantine_version_ids
declare -A resolution_case_ids
declare -A quality_issue_ids
for project in "${browser_projects[@]}"; do
  source_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
  ingestion_run_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
  source_asset_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
  source_version_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
  quarantine_asset_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
  quarantine_version_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
  quarantine_decision_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
  resolution_source_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
  resolution_candidate_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
  resolution_profile_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
  resolution_case_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
  resolution_link_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
  resolution_decision_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
  publication_identifier_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
  publication_asset_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
  publication_version_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
  publication_document_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
  publication_extraction_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
  publication_fact_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
  publication_review_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
  quality_snapshot_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
  quality_issue_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
  quality_event_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
  publication_identifier=$(python3 -c 'import hashlib, sys; print(("P" + hashlib.sha256(sys.argv[1].encode()).hexdigest().upper())[:10])' "$fixture_key-$project")
  publication_digest=$(python3 -c 'import hashlib, sys; print(hashlib.sha256(sys.argv[1].encode()).hexdigest())' "$fixture_key-$project-publication")
  project_user_id=${project_user_ids[$project]}
  ingestion_run_ids[$project]=$ingestion_run_id
  quarantine_version_ids[$project]=$quarantine_version_id
  resolution_case_ids[$project]=$resolution_case_id
  quality_issue_ids[$project]=$quality_issue_id
  if [[ -z "${MSYSTEM:-}" ]]; then
    mkdir -p "$fixture_source_root/$project"
  fi
  docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -v ON_ERROR_STOP=1 >/dev/null <<SQL
BEGIN;
INSERT INTO data_sources (
  id, tenant_id, name, source_type, root_uri, owner, data_classification,
  authorization_scopes, authorization_valid_from, dataset_key, include_globs,
  exclude_globs, routing_rules, stable_seconds, max_file_bytes,
  scan_interval_seconds, expected_freshness_seconds, rate_limit_per_minute,
  state, config_version, connector_cursor, last_scanned_at, consecutive_failures, created_at, updated_at
) VALUES (
  '$source_id', '$tenant_id', 'Browser replay $fixture_key $project', 'FOLDER',
  '/sources/knowledge/.browser-$fixture_key/$project', 'Browser Data Operations', 'internal',
  '["contract:browser-acceptance"]'::json, now(), '$dataset_key', '["*","**/*"]'::json,
  '[]'::json, '[]'::json, 0, 1048576, 3600, 86400, 60,
  'ACTIVE', 1, '{}'::json, now(), 1, now(), now()
);
INSERT INTO ingestion_runs (
  id, tenant_id, data_source_id, workflow_id, state, started_at, completed_at,
  heartbeat_at, counters, result, error_summary, created_at
) VALUES (
  '$ingestion_run_id', '$tenant_id', '$source_id', 'browser-replay-$fixture_key-$project',
  'FAILED', now(), now(), now(), '{"failed":1}'::json, '{"version_ids":[]}'::json,
  'Controlled browser recovery fixture', now()
);
INSERT INTO source_assets (
  id, tenant_id, data_source_id, logical_path, source_uri, file_name, extension,
  media_type, processing_mode, state, first_seen_at, last_seen_at, created_at, updated_at
) VALUES (
  '$source_asset_id', '$tenant_id', '$source_id', 'controlled/browser-recovery-$project.md',
  'file:///sources/browser-recovery-$project.md', 'browser-recovery-$project.md', '.md',
  'text/markdown', 'parse', 'ACTIVE', now(), now(), now(), now()
);
INSERT INTO source_versions (
  id, tenant_id, source_asset_id, version_number, content_sha256, size_bytes,
  discovered_at, state, snapshot_status, malware_scan_status, parse_status,
  retrieval_status, governance_status, raw_object_uri, malware_scanner,
  malware_signature_version, malware_scanned_at, metadata_json, error_code,
  error_message, quarantine_status, quarantine_version, quarantine_updated_at, created_at
) VALUES (
  '$source_version_id', '$tenant_id', '$source_asset_id', 1,
  'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', 128,
  now(), 'FAILED', 'SUCCEEDED', 'SUCCEEDED', 'FAILED', 'NOT_STARTED', 'NOT_STARTED',
  'file:///controlled/browser-recovery-$project.md', 'clamav', 'browser-fixture', now(),
  '{"malware_scan":{"status":"clean"}}'::json, 'parse_failed',
  'Controlled browser parser failure', 'NOT_APPLICABLE', 0, NULL, now()
);
UPDATE source_assets SET current_version_id = '$source_version_id' WHERE id = '$source_asset_id';
INSERT INTO source_assets (
  id, tenant_id, data_source_id, logical_path, source_uri, file_name, extension,
  media_type, processing_mode, state, first_seen_at, last_seen_at, created_at, updated_at
) VALUES (
  '$quarantine_asset_id', '$tenant_id', '$source_id', 'controlled/browser-quarantine-$project.md',
  'file:///sources/browser-quarantine-$project.md', 'browser-quarantine-$project.md', '.md',
  'text/markdown', 'parse', 'ACTIVE', now(), now(), now(), now()
);
INSERT INTO source_versions (
  id, tenant_id, source_asset_id, version_number, content_sha256, size_bytes,
  discovered_at, state, snapshot_status, malware_scan_status, parse_status,
  retrieval_status, governance_status, raw_object_uri, malware_scanner,
  malware_signature_version, malware_scanned_at, metadata_json, error_code,
  error_message, quarantine_status, quarantine_version, quarantine_updated_at, created_at
) VALUES (
  '$quarantine_version_id', '$tenant_id', '$quarantine_asset_id', 1,
  'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb', 68,
  now(), 'FAILED', 'SUCCEEDED', 'FAILED', 'NOT_STARTED', 'NOT_STARTED', 'NOT_STARTED',
  'file:///controlled/browser-quarantine-$project.md', 'clamav', 'browser-fixture', now(),
  '{"malware_scan":{"status":"detected","threat_name":"Win.Test.EICAR_HDB-1"}}'::json,
  'malware_detected', 'Controlled browser malware detection', 'PENDING_REVIEW', 1, now(), now()
);
UPDATE source_assets SET current_version_id = '$quarantine_version_id' WHERE id = '$quarantine_asset_id';
INSERT INTO source_version_quarantine_decisions (
  id, tenant_id, source_version_id, operation_key, action, expected_version, resulting_version,
  previous_status, resulting_status, reason, actor_type, actor_id, workflow_id, details, created_at
) VALUES (
  '$quarantine_decision_id', '$tenant_id', '$quarantine_version_id',
  'browser:scan-detected:$fixture_key:$project', 'scan_detected', 0, 1,
  'NOT_APPLICABLE', 'PENDING_REVIEW', 'Controlled browser malware detection requires operator review',
  'system', 'browser-acceptance', NULL, '{"threat_name":"Win.Test.EICAR_HDB-1"}'::json, now()
);
INSERT INTO entities (
  id, tenant_id, entity_type, name, normalized_name, description,
  external_ids, attributes, review_status, created_at, updated_at
) VALUES
(
  '$resolution_source_id', '$tenant_id', 'TARGET', 'Browser resolution alias $project',
  'browser resolution alias $project', 'Controlled reversible master-data browser fixture',
  '{"acceptance":"resolution-source-$project"}',
  '{"acceptance_fixture":true,"acceptance_fixture_key":"$fixture_key"}',
  'VERIFIED', now(), now()
),
(
  '$resolution_candidate_id', '$tenant_id', 'TARGET', 'Browser resolution canonical $project',
  'browser resolution canonical $project', 'Controlled reversible master-data browser fixture',
  '{"acceptance":"resolution-candidate-$project"}',
  '{"acceptance_fixture":true,"acceptance_fixture_key":"$fixture_key"}',
  'VERIFIED', now(), now()
);
INSERT INTO target_profiles (
  id, tenant_id, entity_id, gene_symbol, organism, created_at, updated_at
) VALUES (
  '$resolution_profile_id', '$tenant_id', '$resolution_candidate_id',
  'E2E-$project', 'Homo sapiens', now(), now()
);
INSERT INTO entity_resolution_cases (
  id, tenant_id, source_entity_id, candidate_entity_id, score, risk_tier,
  reasons, status, proposed_by, reviewed_by_user_id, reviewed_at, review_notes,
  created_at, updated_at
) VALUES (
  '$resolution_case_id', '$tenant_id', '$resolution_source_id', '$resolution_candidate_id',
  0.98, 'medium', '[{"code":"browser_verified_identifier","weight":0.98}]'::json,
  'APPROVED', 'browser-acceptance', '$project_user_id', now(),
  'Controlled initial merge for browser rollback acceptance', now(), now()
);
INSERT INTO entity_canonical_links (
  id, tenant_id, alias_entity_id, canonical_entity_id, resolution_case_id,
  active, created_at, updated_at
) VALUES (
  '$resolution_link_id', '$tenant_id', '$resolution_source_id', '$resolution_candidate_id',
  '$resolution_case_id', true, now(), now()
);
INSERT INTO entity_resolution_decisions (
  id, tenant_id, resolution_case_id, action, decided_by_user_id, notes, snapshot, created_at
) VALUES (
  '$resolution_decision_id', '$tenant_id', '$resolution_case_id', 'approve', '$project_user_id',
  'Controlled initial merge for browser rollback acceptance',
  '{"alias_entity_id":"$resolution_source_id","canonical_entity_id":"$resolution_candidate_id","expected_status":"pending","impact":{"candidate_reference_count":1}}'::json,
  now()
);
INSERT INTO entity_identifiers (
  id, tenant_id, entity_id, entity_type, namespace, value, normalized_value,
  trusted_namespace, source_document_id, provenance, review_status, created_at, updated_at
) VALUES (
  '$publication_identifier_id', '$tenant_id', '$resolution_candidate_id', 'TARGET', 'uniprot',
  '$publication_identifier', '$publication_identifier', true, NULL,
  '{"origin":"browser-acceptance"}'::json, 'VERIFIED', now(), now()
);
INSERT INTO source_assets (
  id, tenant_id, data_source_id, logical_path, source_uri, file_name, extension,
  media_type, processing_mode, state, first_seen_at, last_seen_at, created_at, updated_at
) VALUES (
  '$publication_asset_id', '$tenant_id', '$source_id', 'controlled/browser-publication-$project.md',
  'file:///sources/browser-publication-$project.md', 'browser-publication-$project.md', '.md',
  'text/markdown', 'parse', 'ACTIVE', now(), now(), now(), now()
);
INSERT INTO source_documents (
  id, tenant_id, title, source_type, source_uri, content_sha256, metadata_json, created_at, updated_at
) VALUES (
  '$publication_document_id', '$tenant_id', 'Browser publication $fixture_key $project', 'folder',
  'file:///sources/browser-publication-$project.md', '$publication_digest',
  '{"acceptance_fixture":true,"acceptance_fixture_key":"$fixture_key"}'::json, now(), now()
);
INSERT INTO source_versions (
  id, tenant_id, source_asset_id, version_number, content_sha256, size_bytes,
  discovered_at, state, snapshot_status, malware_scan_status, parse_status,
  retrieval_status, governance_status, raw_object_uri, source_document_id,
  metadata_json, quarantine_status, quarantine_version, created_at
) VALUES (
  '$publication_version_id', '$tenant_id', '$publication_asset_id', 1,
  '$publication_digest', 256, now(), 'GOVERNANCE_PENDING', 'SUCCEEDED', 'SUCCEEDED',
  'SUCCEEDED', 'SUCCEEDED', 'SUCCEEDED', 'file:///controlled/browser-publication-$project.md',
  '$publication_document_id', '{"acceptance_fixture":true}'::json, 'NOT_APPLICABLE', 0, now()
);
UPDATE source_assets SET current_version_id = '$publication_version_id' WHERE id = '$publication_asset_id';
INSERT INTO extraction_runs (
  id, tenant_id, source_version_id, schema_name, schema_version, model_provider,
  model_name, prompt_sha256, policy_sha256, input_sha256, status,
  structured_output, validation_errors, started_at, completed_at, created_at
) VALUES (
  '$publication_extraction_id', '$tenant_id', '$publication_version_id',
  'pharma_document_facts', '2.12.0', 'browser-acceptance', 'browser-acceptance',
  'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
  'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
  '$publication_digest', 'SUCCEEDED', '{}'::json, '[]'::json, now(), now(), now()
);
INSERT INTO staged_facts (
  id, tenant_id, extraction_run_id, fact_kind, fact_key, raw_payload, payload,
  normalization_version, source_document_id, source_locator, source_quote,
  confidence, status, quality_findings, conflict_with_ids, created_at, updated_at
) VALUES (
  '$publication_fact_id', '$tenant_id', '$publication_extraction_id', 'claim',
  'browser-publication-$fixture_key-$project',
  '{"fixture":"$fixture_key","project":"$project"}'::json,
  '{"subject":{"entity_type":"target","name":"Browser resolution canonical $fixture_key-$project","external_ids":{"uniprot":"$publication_identifier"}},"predicate":"has_browser_publication_evidence","value":{"fixture":"$fixture_key","project":"$project"}}'::json,
  'browser-acceptance-v1', '$publication_document_id', 'page=1',
  'Browser publication evidence $fixture_key $project', 0.99, 'REVIEW_PENDING',
  '[]'::json, '[]'::json, now(), now()
);
INSERT INTO review_tasks (
  id, tenant_id, staged_fact_id, status, priority, reasons, assigned_user_id,
  created_at, updated_at
) VALUES (
  '$publication_review_id', '$tenant_id', '$publication_fact_id', 'REVIEW_PENDING', 1000,
  '[{"code":"browser_human_review_required"}]'::json, '$project_user_id', now(), now()
);
INSERT INTO data_quality_snapshots (
  id, tenant_id, trigger, definitions_version, window_start, window_end,
  measured_at, metrics, created_at
) VALUES (
  '$quality_snapshot_id', '$tenant_id', 'manual', 'browser-$fixture_key',
  now() - interval '24 hours', now(), now(),
  '{
    "completeness":{"label":"解析完整率","value":0.82,"numerator":82,"denominator":100,"applicable":true,"threshold":0.95,"comparison":"gte","status":"failed","severity":"high"},
    "duplicate_rate":{"label":"重复率","value":0.03,"numerator":3,"denominator":100,"applicable":true,"threshold":0.05,"comparison":"lte","status":"passed","severity":"medium"},
    "citation_coverage":{"label":"引用覆盖率","value":0.99,"numerator":99,"denominator":100,"applicable":true,"threshold":0.99,"comparison":"gte","status":"passed","severity":"high"},
    "freshness_coverage":{"label":"来源新鲜度覆盖","value":0.96,"numerator":96,"denominator":100,"applicable":true,"threshold":0.95,"comparison":"gte","status":"passed","severity":"medium"},
    "ingestion_success":{"label":"入库成功率","value":0.97,"numerator":97,"denominator":100,"applicable":true,"threshold":0.95,"comparison":"gte","status":"passed","severity":"high"},
    "drift":{"label":"指标漂移","value":0.04,"numerator":400,"denominator":10000,"applicable":true,"threshold":0.1,"comparison":"lte","status":"passed","severity":"medium"}
  }'::json,
  now()
);
INSERT INTO data_quality_issues (
  id, tenant_id, active_key, metric_key, scope_type, scope_id, status, severity,
  title, description, actual_value, threshold_value, comparison, owner_user_id,
  sla_due_at, detected_at, acknowledged_at, resolved_at, resolution_notes,
  version, last_snapshot_id, created_at, updated_at
) VALUES (
  '$quality_issue_id', '$tenant_id', 'browser:$fixture_key:$project',
  'browser_quality_metric', 'browser_project', '$project', 'open', 'high',
  'Browser quality issue $fixture_key-$project',
  '当前值 82.00%，要求至少 95.00%；样本 82/100。',
  0.82, 0.95, 'gte', NULL, now() + interval '8 hours', now(), NULL, NULL, NULL,
  1, '$quality_snapshot_id', now(), now()
);
INSERT INTO data_quality_issue_events (
  id, tenant_id, issue_id, action, actor_type, actor_id, previous_status,
  resulting_status, details, occurred_at
) VALUES (
  '$quality_event_id', '$tenant_id', '$quality_issue_id', 'opened', 'system',
  'browser-acceptance', NULL, 'open', '{"origin":"browser-acceptance"}'::json, now()
);
COMMIT;
SQL
done

evidence_source_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
evidence_asset_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
evidence_version_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
evidence_document_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
evidence_extraction_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
evidence_fact_id_1=$(python3 -c 'import uuid; print(uuid.uuid4())')
evidence_fact_id_2=$(python3 -c 'import uuid; print(uuid.uuid4())')
evidence_claim_id_1=$(python3 -c 'import uuid; print(uuid.uuid4())')
evidence_claim_id_2=$(python3 -c 'import uuid; print(uuid.uuid4())')
evidence_link_id_1=$(python3 -c 'import uuid; print(uuid.uuid4())')
evidence_link_id_2=$(python3 -c 'import uuid; print(uuid.uuid4())')
knowledge_page_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
knowledge_version_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
knowledge_citation_id_1=$(python3 -c 'import uuid; print(uuid.uuid4())')
knowledge_citation_id_2=$(python3 -c 'import uuid; print(uuid.uuid4())')
evidence_digest=$(python3 -c 'import hashlib, sys; print(hashlib.sha256(sys.argv[1].encode()).hexdigest())' "$fixture_key-governed-evidence")
knowledge_digest=$(python3 -c 'import hashlib, sys; print(hashlib.sha256(sys.argv[1].encode()).hexdigest())' "$fixture_key-governed-knowledge")
docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -v ON_ERROR_STOP=1 >/dev/null <<SQL
BEGIN;
INSERT INTO data_sources (
  id, tenant_id, name, source_type, root_uri, owner, data_classification,
  authorization_scopes, authorization_valid_from, dataset_key, include_globs,
  exclude_globs, routing_rules, stable_seconds, max_file_bytes,
  scan_interval_seconds, expected_freshness_seconds, rate_limit_per_minute,
  state, config_version, connector_cursor, last_scanned_at, consecutive_failures, created_at, updated_at
) VALUES (
  '$evidence_source_id', '$tenant_id', 'Browser evidence $fixture_key', 'FOLDER',
  '/sources/knowledge/.browser-$fixture_key/evidence', 'Browser Data Operations', 'internal',
  '["contract:browser-acceptance"]'::json, now(), '$dataset_key', '["*"]'::json,
  '[]'::json, '[]'::json, 0, 1048576, 3600, 86400, 60,
  'ACTIVE', 1, '{}'::json, now(), 0, now(), now()
);
INSERT INTO source_assets (
  id, tenant_id, data_source_id, logical_path, source_uri, file_name, extension,
  media_type, processing_mode, state, first_seen_at, last_seen_at, created_at, updated_at
) VALUES (
  '$evidence_asset_id', '$tenant_id', '$evidence_source_id', 'controlled/browser-evidence.md',
  'file:///controlled/browser-evidence-$fixture_key.md', 'browser-evidence.md', '.md',
  'text/markdown', 'parse', 'ACTIVE', now(), now(), now(), now()
);
INSERT INTO source_documents (
  id, tenant_id, title, source_type, source_uri, content_sha256, metadata_json, created_at, updated_at
) VALUES (
  '$evidence_document_id', '$tenant_id', 'Browser evidence $fixture_key EGFR', 'folder',
  'file:///controlled/browser-evidence-$fixture_key.md', '$evidence_digest',
  '{"acceptance_fixture":true,"evidence_fixture":true}'::json, now(), now()
);
INSERT INTO source_versions (
  id, tenant_id, source_asset_id, version_number, content_sha256, size_bytes,
  discovered_at, state, snapshot_status, malware_scan_status, parse_status,
  retrieval_status, governance_status, raw_object_uri, source_document_id,
  metadata_json, quarantine_status, quarantine_version, created_at
) VALUES (
  '$evidence_version_id', '$tenant_id', '$evidence_asset_id', 1, '$evidence_digest', 512,
  now(), 'GOVERNANCE_PENDING', 'SUCCEEDED', 'SUCCEEDED', 'SUCCEEDED',
  'SUCCEEDED', 'SUCCEEDED', 'file:///controlled/browser-evidence-$fixture_key.md',
  '$evidence_document_id', '{"acceptance_fixture":true,"evidence_fixture":true}'::json,
  'NOT_APPLICABLE', 0, now()
);
UPDATE source_assets SET current_version_id = '$evidence_version_id' WHERE id = '$evidence_asset_id';
INSERT INTO extraction_runs (
  id, tenant_id, source_version_id, schema_name, schema_version, model_provider,
  model_name, prompt_sha256, policy_sha256, input_sha256, status,
  structured_output, validation_errors, started_at, completed_at, created_at
) VALUES (
  '$evidence_extraction_id', '$tenant_id', '$evidence_version_id', 'pharma_document_facts', '2.12.0',
  'browser-acceptance-evidence', 'browser-acceptance-evidence',
  'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
  'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
  '$evidence_digest', 'SUCCEEDED', '{}'::json, '[]'::json, now(), now(), now()
);
INSERT INTO staged_facts (
  id, tenant_id, extraction_run_id, fact_kind, fact_key, raw_payload, payload,
  normalization_version, source_document_id, source_locator, source_quote,
  confidence, status, quality_findings, conflict_with_ids,
  published_resource_type, published_resource_id, created_at, updated_at
) VALUES
(
  '$evidence_fact_id_1', '$tenant_id', '$evidence_extraction_id', 'claim',
  'browser-evidence-$fixture_key-1',
  '{"fixture":"browser-evidence"}'::json,
  '{"subject":{"entity_type":"target","name":"EGFR"},"predicate":"has_browser_evidence","value":{"marker":"target activity"}}'::json,
  'browser-acceptance-v1', '$evidence_document_id', 'page=1',
  'EGFR governed evidence reports target activity.', 0.99, 'PUBLISHED', '[]'::json, '[]'::json,
  'evidence_claim', '$evidence_claim_id_1', now(), now()
),
(
  '$evidence_fact_id_2', '$tenant_id', '$evidence_extraction_id', 'claim',
  'browser-evidence-$fixture_key-2',
  '{"fixture":"browser-evidence"}'::json,
  '{"subject":{"entity_type":"target","name":"EGFR"},"predicate":"has_browser_evidence","value":{"marker":"competitive landscape"}}'::json,
  'browser-acceptance-v1', '$evidence_document_id', 'page=2',
  'EGFR governed evidence describes the competitive landscape.', 0.98, 'PUBLISHED', '[]'::json, '[]'::json,
  'evidence_claim', '$evidence_claim_id_2', now(), now()
);
INSERT INTO evidence_claims (
  id, tenant_id, subject_id, predicate, object_id, value, source_document_id,
  page_number, source_locator, quote, confidence, review_status, created_at, updated_at
) VALUES
(
  '$evidence_claim_id_1', '$tenant_id', '$pipeline_target_id', 'has_browser_evidence', NULL,
  '{"marker":"target activity"}'::json, '$evidence_document_id', 1, 'page=1',
  'EGFR governed evidence reports target activity.', 0.99, 'VERIFIED', now(), now()
),
(
  '$evidence_claim_id_2', '$tenant_id', '$pipeline_target_id', 'has_browser_evidence', NULL,
  '{"marker":"competitive landscape"}'::json, '$evidence_document_id', 2, 'page=2',
  'EGFR governed evidence describes the competitive landscape.', 0.98, 'VERIFIED', now(), now()
);
INSERT INTO fact_provenance_links (
  id, tenant_id, resource_type, resource_id, staged_fact_id, evidence_claim_id,
  source_asset_id, source_version_id, source_document_id, dataset_key, source_locator, created_at
) VALUES
(
  '$evidence_link_id_1', '$tenant_id', 'evidence_claim', '$evidence_claim_id_1', '$evidence_fact_id_1',
  '$evidence_claim_id_1', '$evidence_asset_id', '$evidence_version_id', '$evidence_document_id', '$dataset_key', 'page=1', now()
),
(
  '$evidence_link_id_2', '$tenant_id', 'evidence_claim', '$evidence_claim_id_2', '$evidence_fact_id_2',
  '$evidence_claim_id_2', '$evidence_asset_id', '$evidence_version_id', '$evidence_document_id', '$dataset_key', 'page=2', now()
);
INSERT INTO knowledge_pages (
  id, tenant_id, page_key, page_type, title, subject_entity_id, status, current_version_id, created_at, updated_at
) VALUES (
  '$knowledge_page_id', '$tenant_id', 'browser/$fixture_key/egfr', 'target',
  'Browser EGFR knowledge $fixture_key', '$pipeline_target_id', 'PUBLISHED', '$knowledge_version_id', now(), now()
);
INSERT INTO knowledge_page_versions (
  id, tenant_id, knowledge_page_id, version_number, compiler_version, content_json,
  rendered_markdown, content_sha256, source_snapshot_at, created_by_run_id, created_at
) VALUES (
  '$knowledge_version_id', '$tenant_id', '$knowledge_page_id', 1, 'browser-acceptance-v1',
  '{"facts":[{"id":"browser-fact-1","predicate":"has_browser_evidence","object_entity":null,"value":{"marker":"target activity"},"confidence":0.99,"citation":1},{"id":"browser-fact-2","predicate":"has_browser_evidence","object_entity":null,"value":{"marker":"competitive landscape"},"confidence":0.98,"citation":2}],"sources":[{"number":1,"document_id":"$evidence_document_id","title":"Browser evidence $fixture_key EGFR","source_uri":"file:///controlled/browser-evidence-$fixture_key.md","locator":"page=1"},{"number":2,"document_id":"$evidence_document_id","title":"Browser evidence $fixture_key EGFR","source_uri":"file:///controlled/browser-evidence-$fixture_key.md","locator":"page=2"}]}'::json,
  E'# Browser EGFR knowledge $fixture_key\n\n- Target activity [1]\n- Competitive landscape [2]',
  '$knowledge_digest', now(), 'browser-acceptance', now()
);
INSERT INTO knowledge_citations (
  id, tenant_id, page_version_id, ordinal, source_document_id, evidence_claim_id, source_locator, quote
) VALUES
(
  '$knowledge_citation_id_1', '$tenant_id', '$knowledge_version_id', 1, '$evidence_document_id',
  '$evidence_claim_id_1', 'page=1', 'EGFR governed evidence reports target activity.'
),
(
  '$knowledge_citation_id_2', '$tenant_id', '$knowledge_version_id', 2, '$evidence_document_id',
  '$evidence_claim_id_2', 'page=2', 'EGFR governed evidence describes the competitive landscape.'
);
COMMIT;
SQL
printf 'evidence|%s:claim:%s\n' "$tenant_id" "$evidence_claim_id_1" >> "$projection_ids_path"
printf 'evidence|%s:claim:%s\n' "$tenant_id" "$evidence_claim_id_2" >> "$projection_ids_path"
printf 'knowledge|%s:%s\n' "$tenant_id" "$knowledge_page_id" >> "$projection_ids_path"
docker compose up -d --no-deps --force-recreate worker >/dev/null
pause_worker_for_cleanup
docker compose run --rm --no-deps worker pharma-search rebuild --build-id "browser-$run_id" >/dev/null
resume_worker_after_cleanup
wait_for_worker_healthy

base_url="${E2E_BASE_URL:-http://127.0.0.1:18380}"
browser_executable=${E2E_BROWSER_EXECUTABLE:-${E2E_CHROME_EXECUTABLE:-}}
browser_channel=chrome
browser_product="Google Chrome"
browser_version_pattern='^Google Chrome [0-9]+([.][0-9]+){3}$'
if [[ $browser_target == chrome ]]; then
  if [[ -z "$browser_executable" ]] && command -v google-chrome >/dev/null 2>&1; then
    browser_executable=$(command -v google-chrome)
  fi
  if [[ -z "$browser_executable" ]]; then
    chrome_cache=${PHARMA_CHROME_CACHE_DIR:-"$HOME/.cache/pharma-intelligence/google-chrome"}
    release_file="$chrome_cache/current"
    if [[ -f "$release_file" && ! -L "$release_file" ]]; then
      browser_release=$(<"$release_file")
      [[ "$browser_release" =~ ^[0-9]+([.][0-9]+){3}-[0-9]+$ ]] || {
        echo "user-level Google Chrome current release is invalid" >&2
        exit 1
      }
      browser_executable="$chrome_cache/releases/$browser_release/opt/google/chrome/google-chrome"
    fi
  fi
  unavailable_message="Google Chrome is unavailable; run ./scripts/bootstrap-wsl-chrome.sh"
else
  browser_channel=msedge
  browser_product="Microsoft Edge"
  browser_version_pattern='^Microsoft Edge [0-9]+([.][0-9]+){3}( unknown)?$'
  edge_track=${browser_target#edge-}
  edge_cache=${PHARMA_EDGE_CACHE_DIR:-"$HOME/.cache/pharma-intelligence/microsoft-edge"}
  release_file="$edge_cache/$edge_track"
  if [[ -z "$browser_executable" && -f "$release_file" && ! -L "$release_file" ]]; then
    browser_release=$(<"$release_file")
    [[ "$browser_release" =~ ^[0-9]+([.][0-9]+){3}-[0-9]+$ ]] || {
      echo "user-level Microsoft Edge $edge_track release is invalid" >&2
      exit 1
    }
    browser_executable="$edge_cache/releases/$browser_release/opt/microsoft/msedge/msedge"
  fi
  unavailable_message="Microsoft Edge $edge_track is unavailable; run ./scripts/bootstrap-wsl-edge.sh --track $edge_track"
fi
[[ -n "$browser_executable" && "$browser_executable" = /* && -x "$browser_executable" ]] || {
  echo "$unavailable_message" >&2
  exit 1
}
browser_executable=$(realpath "$browser_executable")
browser_launch_executable="$browser_executable"
if [[ -n "${MSYSTEM:-}" && -x "$(command -v cygpath || true)" ]]; then
  browser_launch_executable=$(cygpath -w "$browser_executable")
  browser_version="${browser_product} $(powershell.exe -NoProfile -Command "(Get-Item -LiteralPath '$browser_launch_executable').VersionInfo.ProductVersion" | tr -d '\r\n')"
else
  browser_version=$($browser_executable --version)
fi
while [[ "$browser_version" == *[[:space:]] ]]; do
  browser_version=${browser_version%?}
done
[[ "$browser_version" =~ $browser_version_pattern ]] || {
  echo "$browser_product returned an invalid version string: $browser_version" >&2
  exit 1
}
browser_version=${browser_version% unknown}
expected_browser_version=${browser_version#"$browser_product "}
playwright_output_dir="$output_dir"
playwright_json_output_file="$output_dir/results.json"
if [[ -n "${MSYSTEM:-}" && -x "$(command -v cygpath || true)" ]]; then
  playwright_output_dir=$(cygpath -w "$output_dir")
  playwright_json_output_file=$(cygpath -w "$output_dir/results.json")
fi
started_ns=$(date +%s%N)
playwright_args=(
  --reporter=line,json
  --fail-on-flaky-tests
  "--workers=$browser_workers"
  --output="$playwright_output_dir"
)
if [[ "$update_snapshots" == true ]]; then
  playwright_args+=(--update-snapshots=all)
fi
run_playwright() {
  if [[ -n "${E2E_PLAYWRIGHT_COMMAND:-}" ]]; then
    (
      cd "${E2E_PLAYWRIGHT_WORKDIR:-apps/web}"
      "$E2E_PLAYWRIGHT_COMMAND" test "${playwright_args[@]}"
    )
  else
    corepack "$package_manager" --dir apps/web exec playwright test "${playwright_args[@]}"
  fi
}
sync_updated_snapshots() {
  [[ "$update_snapshots" == true && -n "${E2E_PLAYWRIGHT_COMMAND:-}" ]] || return 0
  local source_dir="${E2E_PLAYWRIGHT_WORKDIR:-apps/web}/e2e/visual-baselines"
  local target_dir="$ROOT_DIR/apps/web/e2e/visual-baselines"
  # An alternate launcher can still execute this exact checkout. In that case
  # Playwright already wrote the owned baseline and copying it onto itself fails.
  if [[ "$(realpath -- "$source_dir")" == "$(realpath -- "$target_dir")" ]]; then
    return 0
  fi
  local source_path="$source_dir"
  local target_path="$target_dir"
  if [[ -n "${MSYSTEM:-}" && -x "$(command -v cygpath || true)" ]]; then
    source_path=$(cygpath -w "$source_dir")
    target_path=$(cygpath -w "$target_dir")
  fi
  python3 - "$source_path" "$target_path" <<'PY'
from __future__ import annotations

import shutil
import sys
from pathlib import Path

source_dir, target_dir = map(Path, sys.argv[1:])
expected = {
    "research-workbench-desktop-1440.png",
    "research-workbench-desktop-1920.png",
    "research-workbench-tablet-1024.png",
    "research-workbench-mobile-390.png",
    "research-dense-results-desktop-1440.png",
    "research-dense-results-desktop-1920.png",
    "research-dense-results-tablet-1024.png",
    "research-dense-results-mobile-390.png",
    "research-trial-outcomes-desktop-1440.png",
    "research-trial-outcomes-desktop-1920.png",
    "research-trial-outcomes-tablet-1024.png",
    "research-trial-outcomes-mobile-390.png",
    "research-patent-timeline-desktop-1440.png",
    "research-patent-timeline-desktop-1920.png",
    "research-patent-timeline-tablet-1024.png",
    "research-patent-timeline-mobile-390.png",
    "research-deal-rights-desktop-1440.png",
    "research-deal-rights-desktop-1920.png",
    "research-deal-rights-tablet-1024.png",
    "research-deal-rights-mobile-390.png",
}
if not source_dir.is_dir() or not target_dir.is_dir():
    raise SystemExit("snapshot synchronization directories are missing")
for name in sorted(expected):
    source = source_dir / name
    target = target_dir / name
    if not source.is_file() or source.is_symlink():
        raise SystemExit(f"generated snapshot is missing or unsafe: {name}")
    shutil.copyfile(source, target)
PY
}
CI=1 \
  E2E_BROWSER_CHANNEL="$browser_channel" \
  E2E_BROWSER_EXECUTABLE="$browser_launch_executable" \
  E2E_EXPECTED_BROWSER_PRODUCT="$browser_product" \
  E2E_EXPECTED_BROWSER_VERSION="$expected_browser_version" \
  E2E_BASE_URL="$base_url" \
  E2E_EMAIL_PREFIX="$email_prefix" \
  E2E_PASSWORD="$password" \
  E2E_PERMISSION_EMAIL="$permission_email" \
  E2E_PERMISSION_PASSWORD="$permission_password" \
  E2E_FIXTURE_KEY="$fixture_key" \
  E2E_SEARCH_TARGET_ID_DESKTOP_1440="${search_target_ids[desktop-1440]}" \
  E2E_SEARCH_TARGET_ID_DESKTOP_1920="${search_target_ids[desktop-1920]}" \
  E2E_SEARCH_TARGET_ID_TABLET_1024="${search_target_ids[tablet-1024]}" \
  E2E_SEARCH_TARGET_ID_MOBILE_390="${search_target_ids[mobile-390]}" \
  E2E_SEARCH_COMPANY_ID_DESKTOP_1440="${search_company_ids[desktop-1440]}" \
  E2E_SEARCH_COMPANY_ID_DESKTOP_1920="${search_company_ids[desktop-1920]}" \
  E2E_SEARCH_COMPANY_ID_TABLET_1024="${search_company_ids[tablet-1024]}" \
  E2E_SEARCH_COMPANY_ID_MOBILE_390="${search_company_ids[mobile-390]}" \
  E2E_PIPELINE_TARGET_ID="$pipeline_target_id" \
  E2E_PIPELINE_COMBINATION_TARGET_ID="$pipeline_combination_target_id" \
  E2E_PIPELINE_DRUG_B_ID="$pipeline_drug_b_id" \
  E2E_PIPELINE_DISEASE_ID="$regulatory_indication_id" \
  E2E_EPIDEMIOLOGY_DISEASE_ID="$epidemiology_disease_id" \
  E2E_EPIDEMIOLOGY_PATIENT_POPULATION_ID="$epidemiology_patient_population_id" \
  E2E_EPIDEMIOLOGY_OBSERVATION_ID="$epidemiology_observation_id" \
  E2E_EPIDEMIOLOGY_COMPARABLE_OBSERVATION_ID="$epidemiology_comparable_observation_id" \
  E2E_EPIDEMIOLOGY_INCOMPATIBLE_OBSERVATION_ID="$epidemiology_incompatible_observation_id" \
  E2E_TRIAL_PROFILE_ID="$trial_profile_id" \
  E2E_TRIAL_NEGATIVE_PROFILE_ID="$trial_negative_profile_id" \
  E2E_PIPELINE_ORGANIZATION_ID="$regulatory_company_id" \
  E2E_PIPELINE_COLLABORATOR_ID="$pipeline_company_b_id" \
  E2E_REGULATORY_SUBJECT_ID="$regulatory_subject_id" \
  E2E_REGULATORY_INDICATION_ID="$regulatory_indication_id" \
  E2E_REGULATORY_EVENT_ID="$regulatory_event_id" \
  E2E_REGULATORY_NEGATIVE_EVENT_ID="$regulatory_negative_event_id" \
  E2E_PATENT_FAMILY_ID="$patent_family_id" \
  E2E_PATENT_NEGATIVE_FAMILY_ID="$patent_negative_family_id" \
  E2E_NEWS_EVENT_ID="$news_event_id" \
  E2E_NEWS_NEGATIVE_EVENT_ID="$news_negative_event_id" \
  E2E_DEAL_ENTITY_ID="$deal_entity_id" \
  E2E_DEAL_PROFILE_ID="$deal_profile_id" \
  E2E_INGESTION_RUN_ID_DESKTOP_1440="${ingestion_run_ids[desktop-1440]}" \
  E2E_INGESTION_RUN_ID_DESKTOP_1920="${ingestion_run_ids[desktop-1920]}" \
  E2E_INGESTION_RUN_ID_TABLET_1024="${ingestion_run_ids[tablet-1024]}" \
  E2E_INGESTION_RUN_ID_MOBILE_390="${ingestion_run_ids[mobile-390]}" \
  E2E_QUARANTINE_VERSION_ID_DESKTOP_1440="${quarantine_version_ids[desktop-1440]}" \
  E2E_QUARANTINE_VERSION_ID_DESKTOP_1920="${quarantine_version_ids[desktop-1920]}" \
  E2E_QUARANTINE_VERSION_ID_TABLET_1024="${quarantine_version_ids[tablet-1024]}" \
  E2E_QUARANTINE_VERSION_ID_MOBILE_390="${quarantine_version_ids[mobile-390]}" \
  E2E_RESOLUTION_CASE_ID_DESKTOP_1440="${resolution_case_ids[desktop-1440]}" \
  E2E_RESOLUTION_CASE_ID_DESKTOP_1920="${resolution_case_ids[desktop-1920]}" \
  E2E_RESOLUTION_CASE_ID_TABLET_1024="${resolution_case_ids[tablet-1024]}" \
  E2E_RESOLUTION_CASE_ID_MOBILE_390="${resolution_case_ids[mobile-390]}" \
  E2E_QUALITY_ISSUE_ID_DESKTOP_1440="${quality_issue_ids[desktop-1440]}" \
  E2E_QUALITY_ISSUE_ID_DESKTOP_1920="${quality_issue_ids[desktop-1920]}" \
  E2E_QUALITY_ISSUE_ID_TABLET_1024="${quality_issue_ids[tablet-1024]}" \
  E2E_QUALITY_ISSUE_ID_MOBILE_390="${quality_issue_ids[mobile-390]}" \
  E2E_QUALITY_OWNER_ID_DESKTOP_1440="${project_user_ids[desktop-1440]}" \
  E2E_QUALITY_OWNER_ID_DESKTOP_1920="${project_user_ids[desktop-1920]}" \
  E2E_QUALITY_OWNER_ID_TABLET_1024="${project_user_ids[tablet-1024]}" \
  E2E_QUALITY_OWNER_ID_MOBILE_390="${project_user_ids[mobile-390]}" \
  PLAYWRIGHT_JSON_OUTPUT_FILE="$playwright_json_output_file" \
  run_playwright
sync_updated_snapshots
finished_ns=$(date +%s%N)
duration_ms=$(((finished_ns - started_ns) / 1000000))

python3 - "$output_dir/results.json" "$output_dir/result-counts" "$output_dir/browser-quality.json" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

report_path, counts_path, quality_path = map(Path, sys.argv[1:])
report = json.loads(report_path.read_text(encoding="utf-8"))
stats = report.get("stats")
if not isinstance(stats, dict):
    raise SystemExit("Playwright JSON report is missing stats")
expected = stats.get("expected")
unexpected = stats.get("unexpected")
flaky = stats.get("flaky")
skipped = stats.get("skipped")
if not all(isinstance(value, int) for value in (expected, unexpected, flaky, skipped)):
    raise SystemExit("Playwright JSON report has invalid stats")
if expected < 1 or unexpected != 0 or flaky != 0 or skipped != 0:
    raise SystemExit("browser acceptance contains failed, flaky, skipped, or zero tests")

projects = {"desktop-1440": 0, "desktop-1920": 0, "tablet-1024": 0, "mobile-390": 0}
project_report_keys = {
    "desktop-1440": "desktop_1440",
    "desktop-1920": "desktop_1920",
    "tablet-1024": "tablet_1024",
    "mobile-390": "mobile_390",
}
quality_metrics: dict[str, dict[str, int | float]] = {}
scenario_markers = {
    "accessibility": "[accessibility]",
    "accessibility_dossier": "[accessibility-dossier]",
    "public_login": "[public-login]",
    "external_login": "[external-login]",
    "internal_login": "[internal-login]",
    "authenticated_navigation": "[workspace-navigation]",
    "workspace_isolation": "[workspace-isolation]",
    "research_workbench": "[research-workbench]",
    "internal_workbench": "[internal-workbench]",
    "ingestion_replay": "[ingestion-replay]",
    "quarantine_governance": "[quarantine-governance]",
    "master_data_rollback": "[master-data-rollback]",
    "publication_governance": "[publication-governance]",
    "quality_operations": "[quality-operations]",
    "reflow_keyboard": "[reflow-keyboard]",
    "stable_deep_link": "[stable-deep-link]",
    "explorer_quick_detail_continuity": "[explorer-quick-detail-continuity]",
    "knowledge_research_continuity": "[knowledge-research-continuity]",
    "evidence_research_continuity": "[evidence-research-continuity]",
    "data_lifecycle": "[data-lifecycle]",
    "enterprise_administration": "[enterprise-administration]",
    "billing_dispute": "[billing-dispute]",
    "monitoring": "[monitoring]",
    "comparison_export": "[comparison-export]",
    "domain_export": "[domain-export]",
    "result_pagination": "[result-pagination]",
    "result_to_comparison": "[result-to-comparison]",
    "cross_page_comparison": "[cross-page-comparison]",
    "deal_entity_query": "[deal-entity-query]",
    "deal_asset_attribute_query": "[deal-asset-attributes]",
    "deal_asset_multiselect_query": "[deal-asset-multiselect]",
    "deal_full_result_landscape": "[deal-full-result-landscape]",
    "deal_asset_correctness": "[deal-asset-correctness]",
    "patent_result_correctness": "[patent-result-correctness]",
    "session_recovery": "[session-recovery]",
    "permission_boundary": "[permission-boundary]",
    "real_permission_boundary": "[real-permission-boundary]",
    "real_target_dossier": "[real-target-dossier]",
    "loading_empty_error_recovery": "[workspace-states]",
    "chemistry": "[chemistry]",
    "chemistry_real_api": "[chemistry-real-api]",
    "regulatory_intelligence": "[regulatory-intelligence]",
    "regulatory_result_correctness": "[regulatory-result-correctness]",
    "regulatory_subscription": "[regulatory-subscription]",
    "saved_search_maintenance": "[saved-search-maintenance]",
    "epidemiology_news_subscription": "[epidemiology-news-subscription]",
    "news_result_correctness": "[news-result-correctness]",
    "epidemiology_trend_correctness": "[epidemiology-trend-correctness]",
    "pipeline_intelligence": "[pipeline-intelligence]",
    "pipeline_cross_domain_signals": "[pipeline-cross-domain-signals]",
    "pipeline_cross_domain_navigation": "[pipeline-cross-domain-navigation]",
    "pipeline_dense_results": "[pipeline-dense-results]",
    "pipeline_relationship_correctness": "[pipeline-relationship-correctness]",
    "professional_patent_query": "[professional-patent-query]",
    "professional_deal_query": "[professional-deal-query]",
    "professional_regulatory_query": "[professional-regulatory-query]",
    "professional_epidemiology_query": "[professional-epidemiology-query]",
    "professional_news_query": "[professional-news-query]",
    "clinical_full_result_landscape": "[clinical-full-result-landscape]",
    "clinical_result_dense_fields": "[clinical-result-dense-fields]",
    "clinical_normalized_drug_or": "[clinical-normalized-drug-or]",
    "clinical_role_correctness": "[clinical-role-correctness]",
    "clinical_linked_program_correctness": "[clinical-linked-program-correctness]",
    "browser_quality": "[browser-quality]",
    "web_vitals_rum": "[web-vitals-rum]",
    "initial_load_boundary": "[initial-load-boundary]",
    "table_preference_server_continuity": "[table-preference-server-continuity]",
    "query_cancellation": "[query-cancellation]",
    "professional_query_state_matrix": "[professional-query-state-matrix]",
    "professional_error_permission_matrix": "[professional-error-permission-matrix]",
}
scenario_projects = {name: set() for name in scenario_markers}


def visit(suite: object) -> None:
    if not isinstance(suite, dict):
        raise SystemExit("Playwright JSON report contains an invalid suite")
    for spec in suite.get("specs", []):
        title = spec.get("title")
        if not isinstance(title, str):
            raise SystemExit("Playwright JSON report contains an invalid test title")
        for test in spec.get("tests", []):
            project = test.get("projectName")
            if project not in projects:
                raise SystemExit(f"unexpected Playwright project: {project}")
            projects[project] += 1
            for annotation in test.get("annotations", []):
                if not isinstance(annotation, dict) or annotation.get("type") != "browser-quality-metrics":
                    continue
                description = annotation.get("description")
                if not isinstance(description, str):
                    raise SystemExit("browser quality annotation is missing its JSON description")
                if project in quality_metrics:
                    raise SystemExit(f"duplicate browser quality metrics for project: {project}")
                parsed = json.loads(description)
                if not isinstance(parsed, dict):
                    raise SystemExit("browser quality metrics must be an object")
                quality_metrics[project] = parsed
            for scenario, marker in scenario_markers.items():
                if marker in title:
                    scenario_projects[scenario].add(project)
    for child in suite.get("suites", []):
        visit(child)


for suite in report.get("suites", []):
    visit(suite)
if expected != sum(projects.values()) or any(count < 1 for count in projects.values()):
    raise SystemExit("Playwright project counts do not match the executed test total")
required_projects = set(projects)
incomplete = sorted(name for name, covered in scenario_projects.items() if covered != required_projects)
if incomplete:
    raise SystemExit(f"browser acceptance scenarios are incomplete across projects: {', '.join(incomplete)}")
if set(quality_metrics) != required_projects:
    raise SystemExit("browser quality metrics are incomplete across required projects")
for project, metrics in quality_metrics.items():
    if set(metrics) != {"cls", "inp_ms", "interaction_count", "lcp_ms"}:
        raise SystemExit(f"browser quality metrics are invalid for project: {project}")
    cls = metrics["cls"]
    inp_ms = metrics["inp_ms"]
    interaction_count = metrics["interaction_count"]
    lcp_ms = metrics["lcp_ms"]
    numeric = (int, float)
    if (
        not isinstance(cls, numeric)
        or isinstance(cls, bool)
        or not isinstance(inp_ms, numeric)
        or isinstance(inp_ms, bool)
        or not isinstance(interaction_count, int)
        or isinstance(interaction_count, bool)
        or not isinstance(lcp_ms, numeric)
        or isinstance(lcp_ms, bool)
        or cls < 0
        or cls > 0.1
        or inp_ms < 0
        or inp_ms > 200
        or interaction_count < 1
        or lcp_ms <= 0
        or lcp_ms > 2500
    ):
        raise SystemExit(f"browser quality budget failed for project: {project}")
counts_path.write_text(
    f"{expected} {projects['desktop-1440']} {projects['desktop-1920']} "
    f"{projects['tablet-1024']} {projects['mobile-390']} 0 {','.join(sorted(scenario_projects))}\n",
    encoding="ascii",
)
quality_path.write_text(
    json.dumps(
        {project_report_keys[project]: quality_metrics[project] for project in projects},
        indent=2,
        sort_keys=True,
    )
    + "\n",
    encoding="utf-8",
)
PY
read -r total_tests desktop_1440_tests desktop_1920_tests tablet_1024_tests mobile_390_tests failed_tests scenario_names \
  < "$output_dir/result-counts"
quality_json=$(<"$output_dir/browser-quality.json")

python3 - "$update_snapshots" "$browser_version" "$ROOT_DIR/apps/web/e2e/visual-baselines" <<'PY'
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

update = sys.argv[1] == "true"
browser_version = sys.argv[2]
baseline_dir = Path(sys.argv[3])
manifest_path = baseline_dir / "manifest.json"
expected = {
    "research-workbench-desktop-1440.png": ("1440x900", "controlled-no-result", "full-page"),
    "research-workbench-desktop-1920.png": ("1920x1080", "controlled-no-result", "full-page"),
    "research-workbench-tablet-1024.png": ("1024x768", "controlled-no-result", "full-page"),
    "research-workbench-mobile-390.png": ("390x844", "controlled-no-result", "full-page"),
    "research-dense-results-desktop-1440.png": ("1440x900", "controlled-dense-results", "table-shell"),
    "research-dense-results-desktop-1920.png": ("1920x1080", "controlled-dense-results", "table-shell"),
    "research-dense-results-tablet-1024.png": ("1024x768", "controlled-dense-results", "table-shell"),
    "research-dense-results-mobile-390.png": ("390x844", "controlled-dense-results", "table-shell"),
    "research-trial-outcomes-desktop-1440.png": ("1440x900", "controlled-trial-outcomes", "dossier-section"),
    "research-trial-outcomes-desktop-1920.png": ("1920x1080", "controlled-trial-outcomes", "dossier-section"),
    "research-trial-outcomes-tablet-1024.png": ("1024x768", "controlled-trial-outcomes", "dossier-section"),
    "research-trial-outcomes-mobile-390.png": ("390x844", "controlled-trial-outcomes", "dossier-section"),
    "research-patent-timeline-desktop-1440.png": ("1440x900", "controlled-patent-timeline", "dossier-section"),
    "research-patent-timeline-desktop-1920.png": ("1920x1080", "controlled-patent-timeline", "dossier-section"),
    "research-patent-timeline-tablet-1024.png": ("1024x768", "controlled-patent-timeline", "dossier-section"),
    "research-patent-timeline-mobile-390.png": ("390x844", "controlled-patent-timeline", "dossier-section"),
    "research-deal-rights-desktop-1440.png": ("1440x900", "controlled-deal-rights", "dossier-section"),
    "research-deal-rights-desktop-1920.png": ("1920x1080", "controlled-deal-rights", "dossier-section"),
    "research-deal-rights-tablet-1024.png": ("1024x768", "controlled-deal-rights", "dossier-section"),
    "research-deal-rights-mobile-390.png": ("390x844", "controlled-deal-rights", "dossier-section"),
}
files = {}
for name, (viewport, state, capture) in expected.items():
    path = baseline_dir / name
    if not path.is_file() or path.is_symlink():
        raise SystemExit(f"visual baseline is missing or unsafe: {name}")
    files[name] = {
        "viewport": viewport,
        "state": state,
        "capture": capture,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }

if update:
    payload = {
        "schema": "pharma.workbench-visual-baselines.v3",
        "schema_version": 3,
        "generated_at": datetime.now(timezone.utc).date().isoformat(),
        "generator": "scripts/run-browser-acceptance.sh --update-snapshots",
        "browser": browser_version,
        "license": "repository-owned-test-artifact",
        "source": "real local authenticated runtime with controlled no-result, dense-result and professional dossier queries",
        "contains_production_data": False,
        "contains_third_party_brand_assets": False,
        "files": files,
    }
    temporary = manifest_path.with_name(f".{manifest_path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, manifest_path)
else:
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit("visual baseline manifest is missing or invalid") from exc
    if (
        not isinstance(manifest, dict)
        or manifest.get("schema") != "pharma.workbench-visual-baselines.v3"
        or manifest.get("schema_version") != 3
        or manifest.get("generator") != "scripts/run-browser-acceptance.sh --update-snapshots"
        or manifest.get("license") != "repository-owned-test-artifact"
        or manifest.get("source")
        != "real local authenticated runtime with controlled no-result, dense-result and professional dossier queries"
        or manifest.get("contains_production_data") is not False
        or manifest.get("contains_third_party_brand_assets") is not False
        or not isinstance(manifest.get("generated_at"), str)
        or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", manifest["generated_at"]) is None
        or not isinstance(manifest.get("browser"), str)
        or re.fullmatch(r"Google Chrome [0-9]+(?:\.[0-9]+){3}", manifest["browser"]) is None
        or manifest.get("files") != files
    ):
        raise SystemExit("visual baseline manifest does not match the committed PNG inventory")
PY

pause_worker_for_cleanup
cleanup_fixtures
cleanup_account
restore_runtime_projection
resume_worker_after_cleanup
cleanup_completed=true
cleanup_output
trap - EXIT
remaining_accounts=$(
  docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -At -v ON_ERROR_STOP=1 \
    -c "SELECT count(*) FROM users WHERE normalized_email LIKE 'e2e-%@example.test'"
)
if [[ "$remaining_accounts" != "0" ]]; then
  echo "Temporary browser account cleanup failed" >&2
  exit 1
fi
remaining_fixtures=$(
  docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -At -v ON_ERROR_STOP=1 \
    -c "SELECT (SELECT count(*) FROM entities WHERE tenant_id = '$tenant_id' AND attributes ->> 'acceptance_fixture' = 'true') + (SELECT count(*) FROM patient_populations WHERE tenant_id = '$tenant_id' AND attributes ->> 'acceptance_fixture' = 'true')"
)
if [[ "$remaining_fixtures" != "0" ]]; then
  echo "Temporary browser fixture cleanup failed" >&2
  exit 1
fi
remaining_chemistry_fixtures=$(
  docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -At -v ON_ERROR_STOP=1 \
    -c "SELECT count(*) FROM compound_structures WHERE tenant_id = '$tenant_id' AND id = '$regulatory_subject_structure_id'"
)
if [[ "$remaining_chemistry_fixtures" != "0" ]]; then
  echo "Temporary browser chemistry fixture cleanup failed" >&2
  exit 1
fi
remaining_activity_fixtures=$(
  docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -At -v ON_ERROR_STOP=1 \
    -c "SELECT (SELECT count(*) FROM activity_measurements WHERE tenant_id = '$tenant_id' AND source_activity_id LIKE 'E2E-e2e-%') + (SELECT count(*) FROM assays WHERE tenant_id = '$tenant_id' AND source_assay_id LIKE 'E2E-e2e-%')"
)
if [[ "$remaining_activity_fixtures" != "0" ]]; then
  echo "Temporary browser activity fixture cleanup failed" >&2
  exit 1
fi
remaining_governed_fixtures=$(
  docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -At -v ON_ERROR_STOP=1 \
    -c "SELECT (SELECT count(*) FROM knowledge_pages WHERE tenant_id = '$tenant_id' AND page_key LIKE 'browser/e2e-%') + (SELECT count(*) FROM evidence_claims WHERE tenant_id = '$tenant_id' AND source_document_id IN (SELECT id FROM source_documents WHERE tenant_id = '$tenant_id' AND title LIKE 'Browser evidence e2e-%')) + (SELECT count(*) FROM data_sources WHERE tenant_id = '$tenant_id' AND name LIKE 'Browser evidence e2e-%')"
)
if [[ "$remaining_governed_fixtures" != "0" ]]; then
  echo "Temporary governed knowledge/evidence fixture cleanup failed" >&2
  exit 1
fi
remaining_ingestion_fixtures=$(
  docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -At -v ON_ERROR_STOP=1 \
    -c "SELECT count(*) FROM data_sources WHERE tenant_id = '$tenant_id' AND name LIKE 'Browser replay e2e-%'"
)
if [[ "$remaining_ingestion_fixtures" != "0" ]]; then
  echo "Temporary browser ingestion fixture cleanup failed" >&2
  exit 1
fi
remaining_quality_fixtures=$(
  docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -At -v ON_ERROR_STOP=1 \
    -c "SELECT count(*) FROM data_quality_issues WHERE tenant_id = '$tenant_id' AND active_key LIKE 'browser:e2e-%'"
)
if [[ "$remaining_quality_fixtures" != "0" ]]; then
  echo "Temporary browser quality fixture cleanup failed" >&2
  exit 1
fi

if [[ -n "$output_path" ]]; then
  output_parent=$(dirname -- "$output_path")
  output_name=$(basename -- "$output_path")
  [[ "$output_name" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]] || {
    echo "invalid output filename: $output_name" >&2
    exit 2
  }
  mkdir -p "$output_parent"
  output_parent=$(realpath "$output_parent")
  output_path="$output_parent/$output_name"
  python3 - "$output_path" "$base_url" "$browser_version" "$browser_channel" "$browser_product" "$duration_ms" \
    "$total_tests" "$desktop_1440_tests" "$desktop_1920_tests" "$tablet_1024_tests" \
    "$mobile_390_tests" "$failed_tests" "$scenario_names" "$quality_json" \
    "$ROOT_DIR/apps/web/e2e/visual-baselines" <<'PY'
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

output = Path(sys.argv[1])
base_url = sys.argv[2]
browser_version = sys.argv[3]
browser_channel = sys.argv[4]
browser_product = sys.argv[5]
duration_ms = int(sys.argv[6])
total, desktop_1440, desktop_1920, tablet_1024, mobile_390, failed = map(int, sys.argv[7:13])
scenario_names = sys.argv[13].split(",")
quality_metrics = json.loads(sys.argv[14])
baseline_dir = Path(sys.argv[15])
viewports = {
    "desktop_1440": {"project": "desktop-1440", "width": 1440, "height": 900},
    "desktop_1920": {"project": "desktop-1920", "width": 1920, "height": 1080},
    "tablet_1024": {"project": "tablet-1024", "width": 1024, "height": 768},
    "mobile_390": {"project": "mobile-390", "width": 390, "height": 844},
}
visual_projects = {}
for key, viewport in viewports.items():
    no_result = baseline_dir / f"research-workbench-{viewport['project']}.png"
    dense_results = baseline_dir / f"research-dense-results-{viewport['project']}.png"
    trial_outcomes = baseline_dir / f"research-trial-outcomes-{viewport['project']}.png"
    patent_timeline = baseline_dir / f"research-patent-timeline-{viewport['project']}.png"
    deal_rights = baseline_dir / f"research-deal-rights-{viewport['project']}.png"
    if any(
        not path.is_file() or path.is_symlink()
        for path in (no_result, dense_results, trial_outcomes, patent_timeline, deal_rights)
    ):
        raise SystemExit(f"visual baselines are incomplete or unsafe for {viewport['project']}")
    visual_projects[key] = {
        **viewport,
        "baselines": {
            "no_result": {"capture": "full-page", "sha256": hashlib.sha256(no_result.read_bytes()).hexdigest()},
            "dense_results": {
                "capture": "table-shell",
                "sha256": hashlib.sha256(dense_results.read_bytes()).hexdigest(),
            },
            "trial_outcomes": {
                "capture": "dossier-section",
                "sha256": hashlib.sha256(trial_outcomes.read_bytes()).hexdigest(),
            },
            "patent_timeline": {
                "capture": "dossier-section",
                "sha256": hashlib.sha256(patent_timeline.read_bytes()).hexdigest(),
            },
            "deal_rights": {
                "capture": "dossier-section",
                "sha256": hashlib.sha256(deal_rights.read_bytes()).hexdigest(),
            },
        },
    }
temporary = output.with_name(f".{output.name}.{os.getpid()}.tmp")
payload = (
    json.dumps(
        {
            "schema": "pharma.browser-acceptance.v9",
            "schema_version": 9,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "passed",
            "production_claim": False,
            "environment_kind": "local-controlled-browser",
            "base_url": base_url,
            "browser": {
                "channel": browser_channel,
                "product": browser_product,
                "version": browser_version.removeprefix(f"{browser_product} "),
            },
            "tests": {
                "total": total,
                "desktop_1440": desktop_1440,
                "desktop_1920": desktop_1920,
                "tablet_1024": tablet_1024,
                "mobile_390": mobile_390,
                "failed": failed,
            },
            "scenarios": {name: True for name in scenario_names},
            "reflow": {
                "scope": "effective-css-viewport-equivalent",
                "css_widths": [320, 360, 720],
                "system_zoom_verified": False,
            },
            "performance": {
                "scope": "local-controlled-navigation",
                "thresholds": {"lcp_ms": 2500, "inp_ms": 200, "cls": 0.1},
                "projects": quality_metrics,
            },
            "visual_regression": {
                "baseline_kind": "repository-owned-controlled-workbench-states",
                "comparison": "pixel",
                "max_diff_pixel_ratio": 0.001,
                "projects": visual_projects,
            },
            "duration_ms": duration_ms,
            "temporary_accounts_after": 0,
            "temporary_entities_after": 0,
            "temporary_chemistry_fixtures_after": 0,
            "temporary_activity_fixtures_after": 0,
            "temporary_governed_fixtures_after": 0,
            "credentials_recorded": False,
        },
        indent=2,
        sort_keys=True,
    )
    + "\n"
).encode()
descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
try:
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.link(temporary, output, follow_symlinks=False)
    except FileExistsError as exc:
        raise SystemExit(f"refusing to overwrite browser evidence: {output}") from exc
    directory_fd = os.open(output.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
finally:
    temporary.unlink(missing_ok=True)
PY
  printf 'browser_report=%s\n' "$output_path"
fi

printf \
  'BROWSER_ACCEPTANCE status=passed browser=%s tests=%s desktop_1440=%s desktop_1920=%s tablet_1024=%s mobile_390=%s duration_ms=%s snapshots_updated=%s temporary_accounts_after=0 temporary_entities_after=0 temporary_chemistry_fixtures_after=0 temporary_activity_fixtures_after=0 temporary_governed_fixtures_after=0 temporary_ingestion_fixtures_after=0 credentials_recorded=false\n' \
  "$browser_target" "$total_tests" "$desktop_1440_tests" "$desktop_1920_tests" "$tablet_1024_tests" \
  "$mobile_390_tests" "$duration_ms" "$update_snapshots"
