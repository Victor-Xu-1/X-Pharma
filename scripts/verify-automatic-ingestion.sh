#!/usr/bin/env bash
set -Eeuo pipefail

umask 077

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$root"
source_id=""
minimum_files=1
timeout_seconds=900
output_path=""
project_name="${COMPOSE_PROJECT_NAME:-pharma-intelligence}"

usage() {
  cat <<'EOF'
Usage: verify-automatic-ingestion.sh --source-id UUID [options]

Wait for the running Temporal scheduler to process an already registered real
source. The observed run must create an immutable version, reprocess an existing
version under a new AI-governance policy, or prove the source unchanged. This
acceptance never invokes a manual ingest command, creates source content, changes
scan timestamps, or shortens the source interval.

Options:
  --source-id UUID     Existing licensed source to observe.
  --minimum-files N    Required current source versions (default: 1).
  --timeout-seconds N  Maximum wait including the natural due interval (default: 900).
  --output FILE        Write an atomic machine-readable report.
  --project-name NAME  Compose project owning the runtime (default: COMPOSE_PROJECT_NAME
                       or pharma-intelligence).
  -h, --help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --source-id)
      [[ $# -ge 2 ]] || { echo "--source-id requires a value" >&2; exit 2; }
      source_id=$2
      shift 2
      ;;
    --minimum-files)
      [[ $# -ge 2 ]] || { echo "--minimum-files requires a value" >&2; exit 2; }
      minimum_files=$2
      shift 2
      ;;
    --timeout-seconds)
      [[ $# -ge 2 ]] || { echo "--timeout-seconds requires a value" >&2; exit 2; }
      timeout_seconds=$2
      shift 2
      ;;
    --output)
      [[ $# -ge 2 ]] || { echo "--output requires a value" >&2; exit 2; }
      output_path=$2
      shift 2
      ;;
    --project-name)
      [[ $# -ge 2 ]] || { echo "--project-name requires a value" >&2; exit 2; }
      project_name=$2
      shift 2
      ;;
    -h|--help)
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

[[ "$source_id" =~ ^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$ ]] || {
  echo "--source-id must be a UUID" >&2
  exit 2
}
[[ "$minimum_files" =~ ^[1-9][0-9]*$ && "$minimum_files" -le 1000000 ]] || {
  echo "--minimum-files must be between 1 and 1000000" >&2
  exit 2
}
[[ "$timeout_seconds" =~ ^[1-9][0-9]*$ && "$timeout_seconds" -ge 60 && "$timeout_seconds" -le 86400 ]] || {
  echo "--timeout-seconds must be between 60 and 86400" >&2
  exit 2
}
[[ "$project_name" =~ ^[a-z0-9][a-z0-9_-]*$ ]] || {
  echo "--project-name must contain only lowercase letters, digits, underscores or hyphens" >&2
  exit 2
}
for command in docker python3 dirname basename realpath; do
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
# Keep the selected project explicit. This prevents a missing environment
# variable from silently probing a different Compose application.
compose=(docker compose --project-name "$project_name")
for service in worker postgres; do
  container=$("${compose[@]}" ps -q "$service")
  [[ -n "$container" && "$(docker inspect --format '{{.State.Running}}' "$container")" == true ]] || {
    echo "required Compose service is not running: $service (project=$project_name, files=$COMPOSE_FILE)" >&2
    exit 1
  }
done
[[ "$("${compose[@]}" exec -T worker printenv TEMPORAL_ENABLED | tr -d '\r')" == true ]] || {
  echo "worker does not have Temporal enabled" >&2
  exit 1
}
[[ "$("${compose[@]}" exec -T worker printenv TEMPORAL_SCHEDULER_ENABLED | tr -d '\r')" == true ]] || {
  echo "worker does not have the automatic scheduler enabled" >&2
  exit 1
}
ai_governance_enabled=$("${compose[@]}" exec -T worker printenv AI_GOVERNANCE_ENABLED 2>/dev/null | tr -d '\r' || true)
ai_model=$("${compose[@]}" exec -T worker printenv AI_MODEL 2>/dev/null | tr -d '\r' || true)
ai_api_key=$("${compose[@]}" exec -T worker printenv AI_API_KEY 2>/dev/null | tr -d '\r' || true)
[[ "$ai_governance_enabled" == true && -n "$ai_model" && -n "$ai_api_key" ]] || {
  echo "worker does not have a configured AI governance model" >&2
  exit 1
}
unset ai_api_key
ai_policy_sha256=$(
  "${compose[@]}" exec -T worker python -c \
    'from pharma_intel.config import get_settings; from pharma_intel.governance.service import governance_policy_sha256; print(governance_policy_sha256(get_settings()))' \
    | tr -d '\r'
)
[[ "$ai_policy_sha256" =~ ^[0-9a-f]{64}$ ]] || {
  echo "worker returned an invalid AI governance policy fingerprint" >&2
  exit 1
}

pg_user=$("${compose[@]}" exec -T postgres printenv POSTGRES_USER | tr -d '\r')
pg_db=$("${compose[@]}" exec -T postgres printenv POSTGRES_DB | tr -d '\r')
[[ "$pg_user" =~ ^[a-z_][a-z0-9_]*$ && "$pg_db" =~ ^[a-z_][a-z0-9_]*$ ]] || {
  echo "unsafe PostgreSQL identity returned by the runtime" >&2
  exit 1
}
source_record=$(
  "${compose[@]}" exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -At -F $'\t' \
    -v ON_ERROR_STOP=1 \
    -c "SELECT ds.tenant_id, ds.dataset_key, ds.source_type, ds.state,
      ds.scan_interval_seconds,
      CASE WHEN ds.last_scanned_at IS NULL THEN 0
        ELSE greatest(0, ceil(extract(epoch FROM (ds.last_scanned_at
          + make_interval(secs => ds.scan_interval_seconds) - now()))))::bigint END,
      (SELECT count(*) FROM source_versions baseline_version
        JOIN source_assets baseline_asset ON baseline_asset.id = baseline_version.source_asset_id
        WHERE baseline_asset.data_source_id = ds.id),
      (td.license_policy::jsonb)->>'license_id',
      (td.active
        AND (td.license_policy::jsonb)->>'schema_version' = '1.0'
        AND (td.license_policy::jsonb)->'permitted_channels' @> '[\"web\", \"mcp\"]'::jsonb
        AND (NOT (td.license_policy::jsonb) ? 'valid_from'
          OR ((td.license_policy::jsonb)->>'valid_from')::timestamptz <= now())
        AND (NOT (td.license_policy::jsonb) ? 'expires_at'
          OR ((td.license_policy::jsonb)->>'expires_at')::timestamptz > now())
      )::text,
      coalesce(latest_run.id::text, '00000000-0000-0000-0000-000000000000'),
      coalesce(
        to_char(latest_run.created_at AT TIME ZONE 'UTC', 'YYYY-MM-DD\"T\"HH24:MI:SS.US\"Z\"'),
        '1970-01-01T00:00:00.000000Z'
      ),
      (SELECT count(*) FROM extraction_runs er
        JOIN source_versions policy_version ON policy_version.id = er.source_version_id
        JOIN source_assets policy_asset ON policy_asset.id = policy_version.source_asset_id
        WHERE policy_asset.data_source_id = ds.id
          AND er.status = 'SUCCEEDED'
          AND er.policy_sha256 = '$ai_policy_sha256'),
      (SELECT count(*) FROM source_assets inflight_asset
        JOIN source_versions inflight_version ON inflight_version.id = inflight_asset.current_version_id
        WHERE inflight_asset.data_source_id = ds.id
          AND (
            inflight_version.state IN ('DISCOVERED', 'SNAPSHOTTED', 'PARSED', 'GOVERNANCE_PENDING')
            OR inflight_version.snapshot_status = 'RUNNING'
            OR inflight_version.malware_scan_status = 'RUNNING'
            OR inflight_version.parse_status = 'RUNNING'
            OR inflight_version.governance_status = 'RUNNING'
            OR inflight_version.retrieval_status = 'RUNNING'
          ))
      FROM data_sources ds
      JOIN tenant_datasets td ON td.tenant_id = ds.tenant_id AND td.dataset_key = ds.dataset_key
      LEFT JOIN LATERAL (
        SELECT ir.id, ir.created_at FROM ingestion_runs ir
        WHERE ir.data_source_id = ds.id AND ir.workflow_id LIKE 'source-ingest-$source_id-%'
        ORDER BY ir.created_at DESC, ir.id::uuid DESC LIMIT 1
      ) AS latest_run ON true
      WHERE ds.id = '$source_id'"
)
[[ -n "$source_record" && "$(printf '%s\n' "$source_record" | wc -l)" == 1 ]] || {
  echo "registered source and active licensed dataset were not found exactly once: $source_id" >&2
  exit 1
}
IFS=$'\t' read -r tenant_id dataset_key source_type source_state scan_interval due_in_seconds baseline_versions \
  license_id license_valid baseline_run_id baseline_run_created_at baseline_policy_runs inflight_current_versions \
  <<< "$source_record"
[[ "$source_state" == ACTIVE || "$source_state" == UNAVAILABLE ]] || {
  echo "source is not scheduler eligible: $source_state" >&2
  exit 1
}
[[ "$license_valid" == true ]] || {
  echo "source does not have a current Web/MCP license policy" >&2
  exit 1
}
[[ "$tenant_id" =~ ^[0-9a-fA-F-]{36}$ && "$dataset_key" =~ ^[A-Za-z0-9._-]{1,80}$ ]] || {
  echo "source returned unsafe tenant or dataset metadata" >&2
  exit 1
}
[[ "$license_id" =~ ^[A-Za-z0-9][A-Za-z0-9._:-]{2,119}$ ]] || {
  echo "source returned an invalid license identifier" >&2
  exit 1
}
[[ "$source_type" == FOLDER || "$source_type" == HTTP_MANIFEST || "$source_type" == CLINICALTRIALS_GOV || "$source_type" == PUBMED || "$source_type" == S3_SNAPSHOT || "$source_type" == SFTP_SNAPSHOT ]] || {
  echo "source type is not supported by the automatic acceptance: $source_type" >&2
  exit 1
}
[[ "$baseline_run_id" =~ ^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$ ]] || {
  echo "database returned an invalid scheduler baseline run identifier" >&2
  exit 1
}
[[ "$baseline_run_created_at" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{6}Z$ ]] || {
  echo "database returned an invalid scheduler baseline timestamp" >&2
  exit 1
}
[[ "$scan_interval" =~ ^[0-9]+$ && "$due_in_seconds" =~ ^[0-9]+$ \
  && "$baseline_versions" =~ ^[0-9]+$ && "$baseline_policy_runs" =~ ^[0-9]+$ \
  && "$inflight_current_versions" =~ ^[0-9]+$ ]] || {
  echo "source returned invalid scheduling metadata" >&2
  exit 1
}
((inflight_current_versions == 0)) || {
  echo "source has in-flight downstream processing at the acceptance watermark" >&2
  echo "wait for the current pipeline to settle before capturing automatic-ingestion evidence" >&2
  exit 1
}
poll_seconds=$("${compose[@]}" exec -T worker printenv TEMPORAL_SCHEDULER_POLL_SECONDS | tr -d '\r')
[[ "$poll_seconds" =~ ^[1-9][0-9]*$ ]] || {
  echo "worker returned an invalid scheduler poll interval" >&2
  exit 1
}
minimum_execution_window=$((poll_seconds * 2 + 30))
if ((due_in_seconds + minimum_execution_window > timeout_seconds)); then
  echo "source will not become due inside the bounded acceptance window" >&2
  echo "due_in_seconds=$due_in_seconds timeout_seconds=$timeout_seconds" >&2
  exit 1
fi

preflight_json=$("${compose[@]}" exec -T worker pharma-ingest inspect --source-id "$source_id")
started_epoch=$(date +%s)
deadline_epoch=$((started_epoch + timeout_seconds))
observed_run=""
while (( $(date +%s) < deadline_epoch )); do
  observed_run=$(
    "${compose[@]}" exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -At -F $'\t' \
      -v ON_ERROR_STOP=1 \
      -c "SELECT id::text, state, counters::text,
        coalesce(nullif(regexp_replace(error_summary, E'[\\t\\r\\n]+', ' ', 'g'), ''), '__NONE__'),
        workflow_id,
        to_char(created_at AT TIME ZONE 'UTC', 'YYYY-MM-DD\"T\"HH24:MI:SS.US\"Z\"')
        FROM ingestion_runs
        WHERE data_source_id = '$source_id'
          AND workflow_id LIKE 'source-ingest-$source_id-%'
          AND (created_at, id::uuid) > ('$baseline_run_created_at'::timestamptz, '$baseline_run_id'::uuid)
        ORDER BY created_at DESC, id::uuid DESC LIMIT 1"
  )
  if [[ -n "$observed_run" ]]; then
    IFS=$'\t' read -r run_id run_state run_counters run_error workflow_id observed_run_created_at <<< "$observed_run"
    if [[ "$run_state" == SUCCEEDED ]]; then
      break
    fi
    if [[ "$run_state" == FAILED || "$run_state" == CANCELLED ]]; then
      echo "automatically scheduled ingestion failed: ${run_error:-no error summary}" >&2
      exit 1
    fi
  fi
  sleep 5
done
[[ -n "${run_id:-}" && "${run_state:-}" == SUCCEEDED ]] || {
  echo "automatic scheduler did not complete a new ingestion run within $timeout_seconds seconds" >&2
  exit 1
}
[[ "${observed_run_created_at:-}" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{6}Z$ ]] || {
  echo "automatic scheduler returned an invalid observed run timestamp" >&2
  exit 1
}

pipeline_complete=false
processing_failure_grace_seconds=60
processing_failure_observed_epoch=0
while (( $(date +%s) < deadline_epoch )); do
  processing_record=$(
    "${compose[@]}" exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -At -F $'\t' \
      -v ON_ERROR_STOP=1 \
      -c "SELECT
        count(sv.id) FILTER (WHERE sa.processing_mode = 'parse' AND sv.parse_status = 'SUCCEEDED'),
        count(sv.id) FILTER (WHERE sa.processing_mode = 'parse' AND sv.governance_status = 'SUCCEEDED'),
        count(sv.id) FILTER (WHERE sa.processing_mode = 'parse' AND sv.retrieval_status = 'SUCCEEDED'),
        count(sv.id) FILTER (WHERE sv.state = 'FAILED'
          OR sv.snapshot_status = 'FAILED' OR sv.parse_status = 'FAILED'
          OR sv.governance_status = 'FAILED' OR sv.retrieval_status = 'FAILED'),
        coalesce(nullif(regexp_replace(string_agg(
          coalesce(sv.error_code, '') || ':' || coalesce(sv.error_message, ''), '; '
        ) FILTER (WHERE sv.error_code IS NOT NULL OR sv.error_message IS NOT NULL), E'[\t\r\n]+', ' ', 'g'), ''), '__NONE__')
      FROM source_assets sa
      JOIN source_versions sv ON sv.id = sa.current_version_id
      WHERE sa.data_source_id = '$source_id'"
  )
  IFS=$'\t' read -r governable_versions governed_versions projected_versions failed_versions processing_error \
    <<< "$processing_record"
  if [[ ! "$governable_versions" =~ ^[0-9]+$ || ! "$governed_versions" =~ ^[0-9]+$ \
    || ! "$projected_versions" =~ ^[0-9]+$ || ! "$failed_versions" =~ ^[0-9]+$ ]]; then
    echo "automatic ingestion returned invalid downstream processing counters" >&2
    exit 1
  fi
  if ((failed_versions > 0)); then
    now_epoch=$(date +%s)
    if ((processing_failure_observed_epoch == 0)); then
      processing_failure_observed_epoch=$now_epoch
    elif ((now_epoch - processing_failure_observed_epoch >= processing_failure_grace_seconds)); then
      echo "automatic ingestion downstream processing failed: ${processing_error:-no error summary}" >&2
      exit 1
    fi
    sleep 5
    continue
  fi
  processing_failure_observed_epoch=0
  if ((governable_versions >= 1 && governed_versions == governable_versions)); then
    "${compose[@]}" exec -T worker pharma-search drain --max-batches 1000 >/dev/null
    if ((projected_versions == governable_versions)); then
      pipeline_complete=true
      break
    fi
  fi
  sleep 5
done
[[ "$pipeline_complete" == true ]] || {
  echo "automatic ingestion did not complete AI governance and OpenSearch projection within $timeout_seconds seconds" >&2
  exit 1
}

database_json=$(
  "${compose[@]}" exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -At -v ON_ERROR_STOP=1 \
    -c "SELECT json_build_object(
      'source_state', ds.state,
      'assets', count(sa.id),
      'current_versions', count(sv.id),
      'total_versions', (SELECT count(*) FROM source_versions all_version
        JOIN source_assets all_asset ON all_asset.id = all_version.source_asset_id
        WHERE all_asset.data_source_id = ds.id),
      'traceable_versions', count(sv.id) FILTER (WHERE sv.raw_object_uri IS NOT NULL AND sv.source_document_id IS NOT NULL),
      'secure_versions', count(sv.id) FILTER (WHERE sv.malware_scan_status = 'SUCCEEDED'),
      'processed_versions', count(sv.id) FILTER (WHERE
        (sa.processing_mode = 'asset' AND sv.state = 'ASSET_ONLY')
        OR (sa.processing_mode = 'parse' AND sv.parse_status = 'SUCCEEDED')),
      'governable_versions', count(sv.id) FILTER (WHERE sa.processing_mode = 'parse' AND sv.parse_status = 'SUCCEEDED'),
      'governed_versions', count(sv.id) FILTER (WHERE sa.processing_mode = 'parse' AND sv.governance_status = 'SUCCEEDED'),
      'projected_versions', count(sv.id) FILTER (WHERE sa.processing_mode = 'parse' AND sv.retrieval_status = 'SUCCEEDED'),
      'failed_versions', count(sv.id) FILTER (WHERE sv.state = 'FAILED'
        OR sv.snapshot_status = 'FAILED' OR sv.parse_status = 'FAILED'
        OR sv.retrieval_status = 'FAILED' OR sv.governance_status = 'FAILED')
    )::text
    FROM data_sources ds
    LEFT JOIN source_assets sa ON sa.data_source_id = ds.id AND sa.current_version_id IS NOT NULL
    LEFT JOIN source_versions sv ON sv.id = sa.current_version_id
    WHERE ds.id = '$source_id'
    GROUP BY ds.id"
)
governance_json=$(
  "${compose[@]}" exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -At -v ON_ERROR_STOP=1 \
    -c "WITH source_run AS (
      SELECT er.* FROM extraction_runs er
      JOIN source_versions sv ON sv.id = er.source_version_id
      JOIN source_assets sa ON sa.id = sv.source_asset_id
      WHERE sa.data_source_id = '$source_id'
        -- Keep failed runs for audit, but exclude failures superseded by a later
        -- successful run for the same immutable source version from the current gate.
        AND NOT (
          er.status = 'FAILED'
          AND EXISTS (
            SELECT 1 FROM extraction_runs resolved
            WHERE resolved.source_version_id = er.source_version_id
              AND resolved.status = 'SUCCEEDED'
              AND (resolved.created_at, resolved.id) > (er.created_at, er.id)
          )
        )
    ), source_segment AS (
        SELECT segment.value AS value
        FROM source_run er
        CROSS JOIN LATERAL jsonb_array_elements(
          coalesce(er.structured_output::jsonb->'segments', '[]'::jsonb)
        ) AS segment(value)
        WHERE er.status = 'SUCCEEDED'
      ), source_fact AS (
        SELECT sf.* FROM staged_facts sf
        JOIN source_run er ON er.id = sf.extraction_run_id
      )
      SELECT json_build_object(
        'response_models', (SELECT coalesce(json_agg(DISTINCT model_name ORDER BY model_name), '[]'::json)
          FROM source_run WHERE status = 'SUCCEEDED'),
        'extraction_runs', (SELECT count(*) FROM source_run),
        'successful_extraction_runs', (SELECT count(*) FROM source_run WHERE status = 'SUCCEEDED'),
        'failed_extraction_runs', (SELECT count(*) FROM source_run WHERE status = 'FAILED'),
        'input_tokens', (SELECT coalesce(sum(input_tokens), 0) FROM source_run WHERE status = 'SUCCEEDED'),
        'output_tokens', (SELECT coalesce(sum(output_tokens), 0) FROM source_run WHERE status = 'SUCCEEDED'),
        'segments', (SELECT count(*) FROM source_segment),
        'accounted_segments', (SELECT count(*) FROM source_segment
          WHERE nullif(value->>'provider_request_id', '') IS NOT NULL
            AND (value->>'response_sha256') ~ '^[0-9a-f]{64}$'
            AND (value->>'input_tokens') ~ '^[0-9]+$'
            AND (value->>'output_tokens') ~ '^[0-9]+$'),
        'staged_facts', (SELECT count(*) FROM source_fact),
        'quote_verified_facts', (SELECT count(*) FROM source_fact sf
          WHERE sf.source_locator ~ '^chars=[0-9]+-[0-9]+$'
            AND NOT EXISTS (
              SELECT 1 FROM jsonb_array_elements(coalesce(sf.quality_findings::jsonb, '[]'::jsonb)) finding
              WHERE finding->>'code' = 'quote_not_found_in_segment'
            ))
      )::text"
)
observed_policy_runs=$(
  "${compose[@]}" exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -At -v ON_ERROR_STOP=1 \
    -c "SELECT count(*) FROM extraction_runs er
      JOIN source_versions sv ON sv.id = er.source_version_id
      JOIN source_assets sa ON sa.id = sv.source_asset_id
      WHERE sa.data_source_id = '$source_id'
        AND er.status = 'SUCCEEDED'
        AND er.policy_sha256 = '$ai_policy_sha256'"
)
[[ "$observed_policy_runs" =~ ^[0-9]+$ ]] || {
  echo "automatic ingestion returned an invalid current-policy run count" >&2
  exit 1
}
search_json=$("${compose[@]}" exec -T worker pharma-search status)
finished_epoch=$(date +%s)

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
fi

python3 - "$preflight_json" "$database_json" "$governance_json" "$search_json" "$run_counters" "$source_id" "$source_type" \
  "$dataset_key" "$license_id" "$run_id" "$workflow_id" "$scan_interval" "$due_in_seconds" \
  "$baseline_versions" "$minimum_files" "$((finished_epoch - started_epoch))" "$ai_model" "$output_path" \
  "$baseline_run_id" "$baseline_run_created_at" "$observed_run_created_at" "$ai_policy_sha256" \
  "$baseline_policy_runs" "$observed_policy_runs" <<'PY'
from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

(
    preflight_text,
    database_text,
    governance_text,
    search_text,
    counters_text,
    source_id,
    source_type,
    dataset_key,
    license_id,
    run_id,
    workflow_id,
    scan_interval,
    due_in_seconds,
    baseline_versions,
    minimum_files,
    elapsed_seconds,
    configured_model,
    output_text,
    baseline_run_id,
    baseline_run_created_at,
    observed_run_created_at,
    policy_sha256,
    baseline_policy_runs,
    observed_policy_runs,
) = sys.argv[1:]
preflight = json.loads(preflight_text)
database = json.loads(database_text)
governance = json.loads(governance_text)
response_models = governance.pop("response_models", None)
governance["configured_model"] = configured_model
governance["configured_model_runs"] = (
    governance.get("successful_extraction_runs") if response_models == [configured_model] else 0
)
search = json.loads(search_text)
counters = json.loads(counters_text)
minimum = int(minimum_files)
if preflight.get("source_id") != source_id or preflight.get("configuration_error_count") != 0:
    raise SystemExit("automatic acceptance preflight is not bound to a valid source")
if preflight.get("error_count") != 0 or preflight.get("oversized") != 0:
    raise SystemExit("automatic acceptance preflight reported source errors")
versions = database.get("current_versions")
if database.get("source_state") != "ACTIVE" or not isinstance(versions, int) or versions < minimum:
    raise SystemExit("automatic ingestion did not leave the required active source inventory")
total_versions = database.get("total_versions")
baseline_version_count = int(baseline_versions)
if not isinstance(total_versions, int) or isinstance(total_versions, bool):
    raise SystemExit("automatic scheduler returned an invalid immutable version inventory")
new_versions = total_versions - baseline_version_count
baseline_policy_run_count = int(baseline_policy_runs)
observed_policy_run_count = int(observed_policy_runs)
if observed_policy_run_count < baseline_policy_run_count:
    raise SystemExit("automatic scheduler reduced the successful current-policy run inventory")
if new_versions > 0:
    if counters.get("discovered", 0) < 1 or observed_policy_run_count <= baseline_policy_run_count:
        raise SystemExit("automatic scheduler did not report the new immutable source version")
    scheduler_outcome = "new_version"
elif new_versions == 0:
    if observed_policy_run_count > baseline_policy_run_count:
        if counters.get("discovered", 0) < 1:
            raise SystemExit("automatic scheduler did not report the policy-governed source reprocessing")
        scheduler_outcome = "policy_reprocess"
    elif (
        baseline_version_count < minimum
        or counters.get("discovered") != 0
        or counters.get("unchanged", 0) < minimum
    ):
        raise SystemExit("automatic scheduler did not prove an idempotent unchanged source inventory")
    else:
        scheduler_outcome = "unchanged"
else:
    raise SystemExit("automatic scheduler reduced the immutable source version inventory")
if any(database.get(name) != versions for name in ("assets", "traceable_versions", "secure_versions", "processed_versions")):
    raise SystemExit("automatic ingestion did not produce fully governed traceable versions")
if database.get("failed_versions") != 0 or counters.get("failed") != 0 or counters.get("unstable") != 0:
    raise SystemExit("automatic ingestion completed with failed or unstable source objects")
governable = database.get("governable_versions")
if (
    not isinstance(governable, int)
    or governable < 1
    or database.get("governed_versions") != governable
    or database.get("projected_versions") != governable
):
    raise SystemExit("automatic ingestion did not complete AI governance and OpenSearch projection")
integer_governance_fields = (
    "extraction_runs",
    "successful_extraction_runs",
    "failed_extraction_runs",
    "configured_model_runs",
    "input_tokens",
    "output_tokens",
    "segments",
    "accounted_segments",
    "staged_facts",
    "quote_verified_facts",
)
if any(
    not isinstance(governance.get(name), int) or isinstance(governance.get(name), bool)
    for name in integer_governance_fields
):
    raise SystemExit("automatic AI governance accounting contains invalid counters")
extraction_runs = governance["extraction_runs"]
if (
    not isinstance(governance.get("configured_model"), str)
    or not governance["configured_model"]
    or extraction_runs < governable
    or governance["successful_extraction_runs"] != extraction_runs
    or governance["configured_model_runs"] != extraction_runs
    or governance["failed_extraction_runs"] != 0
    or governance["input_tokens"] < 1
    or governance["output_tokens"] < 1
    or governance["segments"] < 1
    or governance["accounted_segments"] != governance["segments"]
    or governance["staged_facts"] < 1
    or not 1 <= governance["quote_verified_facts"] <= governance["staged_facts"]
):
    raise SystemExit("automatic AI governance did not produce fully accounted, quote-located facts")
cluster = search.get("cluster")
deliveries = search.get("deliveries")
if not isinstance(cluster, dict) or cluster.get("available") is not True or cluster.get("cluster_status") != "green":
    raise SystemExit("OpenSearch is unavailable after automatic ingestion")
if not isinstance(deliveries, dict) or any(deliveries.get(name) != 0 for name in ("dead", "retry", "processing")):
    raise SystemExit("search projection queue is not drained after automatic ingestion")
report = {
    "schema": "pharma.automatic-ingestion-evidence.v4",
    "schema_version": 4,
    "generated_at": datetime.now(UTC).isoformat(),
    "status": "passed",
    "environment": "local-wsl",
    "production_claim": False,
    "source_id": source_id,
    "source_type": source_type.lower(),
    "dataset_key": dataset_key,
    "license_id": license_id,
    "trigger": {
        "mode": "temporal-scheduler",
        "outcome": scheduler_outcome,
        "manual_trigger_used": False,
        "source_schedule_mutated": False,
        "source_content_created_by_test": False,
        "scan_interval_seconds": int(scan_interval),
        "initial_due_in_seconds": int(due_in_seconds),
        "observed_elapsed_seconds": int(elapsed_seconds),
        "baseline_versions": baseline_version_count,
        "observed_versions": total_versions,
        "new_versions": new_versions,
        "baseline_run_id": baseline_run_id,
        "baseline_run_created_at": baseline_run_created_at,
        "observed_run_created_at": observed_run_created_at,
        "policy_sha256": policy_sha256,
        "baseline_policy_runs": baseline_policy_run_count,
        "observed_policy_runs": observed_policy_run_count,
    },
    "workflow": {"run_id": run_id, "workflow_id": workflow_id, "state": "SUCCEEDED", "counters": counters},
    "versions": {
        "current": versions,
        "traceable": database["traceable_versions"],
        "malware_scanned": database["secure_versions"],
        "processed": database["processed_versions"],
        "governable": governable,
        "governed": database["governed_versions"],
        "projected": database["projected_versions"],
        "failed": database["failed_versions"],
    },
    "governance": governance,
    "search": {"cluster": cluster, "deliveries": deliveries},
}
payload = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode()
if output_text:
    output = Path(output_text)
    temporary = output.with_name(f".{output.name}.{os.getpid()}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, output, follow_symlinks=False)
        except FileExistsError as exc:
            raise SystemExit(f"refusing to overwrite automatic ingestion evidence: {output}") from exc
        directory_fd = os.open(output.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temporary.unlink(missing_ok=True)
sys.stdout.buffer.write(payload)
PY

if [[ -n "$output_path" ]]; then
  printf 'automatic_ingestion_report=%s\n' "$output_path"
fi
