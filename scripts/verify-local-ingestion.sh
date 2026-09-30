#!/usr/bin/env bash
set -Eeuo pipefail

umask 077

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$root"
source_id=""
minimum_files=1
output_path=""
started_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
project_name="${COMPOSE_PROJECT_NAME:-pharma-intelligence}"

usage() {
  cat <<'EOF'
Usage: verify-local-ingestion.sh --source-id UUID [--minimum-files N] [--output FILE] [--project-name NAME]

Run an already registered read-only source twice through the real WSL data
factory. Verify connector discovery, snapshot, parsing/asset registration,
AI governance accounting, server-located quotes, provenance, idempotence,
findings, and the rebuildable OpenSearch projection.
This script never creates source files or objects and never registers a synthetic source.
--project-name NAME selects the Compose project owning the running runtime
(default: COMPOSE_PROJECT_NAME or pharma-intelligence).
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

[[ "$source_id" =~ ^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$ ]] || {
  echo "--source-id must be a UUID" >&2
  exit 2
}
[[ "$minimum_files" =~ ^[1-9][0-9]*$ && "$minimum_files" -le 1000000 ]] || {
  echo "--minimum-files must be between 1 and 1000000" >&2
  exit 2
}
[[ "$project_name" =~ ^[a-z0-9][a-z0-9_-]*$ ]] || {
  echo "--project-name must contain only lowercase letters, digits, underscores or hyphens" >&2
  exit 2
}
for command in docker python3 dirname basename realpath mktemp; do
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
compose=(docker compose --project-name "$project_name")
for service in worker postgres; do
  container=$("${compose[@]}" ps -q "$service")
  [[ -n "$container" && "$(docker inspect --format '{{.State.Running}}' "$container")" == true ]] || {
    echo "required Compose service is not running: $service (project=$project_name, files=$COMPOSE_FILE)" >&2
    exit 1
  }
done

ai_governance_enabled=$("${compose[@]}" exec -T worker printenv AI_GOVERNANCE_ENABLED 2>/dev/null | tr -d '\r' || true)
ai_model=$("${compose[@]}" exec -T worker printenv AI_MODEL 2>/dev/null | tr -d '\r' || true)
ai_api_key=$("${compose[@]}" exec -T worker printenv AI_API_KEY 2>/dev/null | tr -d '\r' || true)
[[ "$ai_governance_enabled" == true && -n "$ai_model" && -n "$ai_api_key" ]] || {
  echo "worker does not have a configured AI governance model" >&2
  exit 1
}
unset ai_api_key

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
      (td.license_policy::jsonb)->>'license_id',
      (td.active
        AND (td.license_policy::jsonb)->>'schema_version' = '1.0'
        AND jsonb_typeof((td.license_policy::jsonb)->'permitted_channels') = 'array'
        AND (td.license_policy::jsonb)->'permitted_channels' @> '[\"web\", \"mcp\"]'::jsonb
        AND (NOT (td.license_policy::jsonb) ? 'valid_from' OR ((td.license_policy::jsonb)->>'valid_from')::timestamptz <= now())
        AND (NOT (td.license_policy::jsonb) ? 'expires_at' OR ((td.license_policy::jsonb)->>'expires_at')::timestamptz > now())
      )::text
      FROM data_sources ds
      JOIN tenant_datasets td ON td.tenant_id = ds.tenant_id AND td.dataset_key = ds.dataset_key
      WHERE ds.id = '$source_id'"
)
[[ -n "$source_record" && "$(printf '%s\n' "$source_record" | wc -l)" == 1 ]] || {
  echo "registered ingestion source and active licensed dataset were not found exactly once: $source_id" >&2
  exit 1
}
IFS=$'\t' read -r tenant_id dataset_key source_type source_state license_id license_valid <<< "$source_record"
[[ "$license_valid" == true ]] || {
  echo "registered ingestion source does not have a current Web/MCP license policy" >&2
  exit 1
}
[[ "$tenant_id" =~ ^[0-9a-fA-F-]{36}$ && "$dataset_key" =~ ^[A-Za-z0-9._-]{1,80}$ && "$license_id" =~ ^[A-Za-z0-9][A-Za-z0-9._:-]{2,119}$ ]] || {
  echo "registered ingestion source has unsafe metadata" >&2
  exit 1
}
[[ "$source_state" == ACTIVE || "$source_state" == UNAVAILABLE ]] || {
  echo "registered ingestion source is not eligible for scanning: $source_state" >&2
  exit 1
}
[[ "$source_type" == FOLDER || "$source_type" == HTTP_MANIFEST || "$source_type" == CLINICALTRIALS_GOV || "$source_type" == PUBMED || "$source_type" == S3_SNAPSHOT || "$source_type" == SFTP_SNAPSHOT ]] || {
  echo "registered ingestion source has unsupported type: $source_type" >&2
  exit 1
}
source_type_value=${source_type,,}

preflight_json=$(
  "${compose[@]}" exec -T worker pharma-ingest inspect --source-id "$source_id"
)

work=$(mktemp -d -t pharma-ingestion-acceptance.XXXXXX)
cleanup() {
  case "$work" in
    /tmp/pharma-ingestion-acceptance.*) rm -rf -- "$work" ;;
    *) echo "refusing to clean unexpected ingestion acceptance workspace: $work" >&2 ;;
  esac
}
trap cleanup EXIT INT TERM

"${compose[@]}" exec -T worker pharma-ingest once --source-id "$source_id"
versions_after_first=$(
  "${compose[@]}" exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -At -v ON_ERROR_STOP=1 \
    -c "SELECT count(*) FROM source_versions sv JOIN source_assets sa ON sa.id = sv.source_asset_id WHERE sa.data_source_id = '$source_id'"
)
"${compose[@]}" exec -T worker pharma-ingest once --source-id "$source_id"
versions_after_second=$(
  "${compose[@]}" exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -At -v ON_ERROR_STOP=1 \
    -c "SELECT count(*) FROM source_versions sv JOIN source_assets sa ON sa.id = sv.source_asset_id WHERE sa.data_source_id = '$source_id'"
)
[[ "$versions_after_first" =~ ^[0-9]+$ && "$versions_after_second" == "$versions_after_first" ]] || {
  echo "second source scan created duplicate versions" >&2
  exit 1
}

"${compose[@]}" exec -T worker pharma-search drain --max-batches 1000 >/dev/null
"${compose[@]}" exec -T worker pharma-search status > "$work/search.json"
chmod 600 "$work/search.json"
"${compose[@]}" exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -At -v ON_ERROR_STOP=1 \
  -c "SELECT json_build_object(
    'source_state', ds.state,
    'assets', count(sa.id),
    'current_versions', count(sv.id),
    'active_assets', count(sa.id) FILTER (WHERE sa.state = 'ACTIVE'),
    'traceable_versions', count(sv.id) FILTER (WHERE sv.raw_object_uri IS NOT NULL AND sv.source_document_id IS NOT NULL),
    'secure_versions', count(sv.id) FILTER (WHERE sv.malware_scan_status = 'SUCCEEDED'),
    'processed_versions', count(sv.id) FILTER (WHERE (sa.processing_mode = 'asset' AND sv.state = 'ASSET_ONLY') OR (sa.processing_mode = 'parse' AND sv.parse_status = 'SUCCEEDED')),
    'governable_versions', count(sv.id) FILTER (WHERE sa.processing_mode = 'parse' AND sv.parse_status = 'SUCCEEDED'),
    'governed_versions', count(sv.id) FILTER (WHERE sa.processing_mode = 'parse' AND sv.governance_status = 'SUCCEEDED'),
    'projected_versions', count(sv.id) FILTER (WHERE sa.processing_mode = 'parse' AND sv.retrieval_status = 'SUCCEEDED'),
    'failed_versions', count(sv.id) FILTER (WHERE sv.state = 'FAILED' OR sv.snapshot_status = 'FAILED' OR sv.parse_status = 'FAILED' OR sv.retrieval_status = 'FAILED' OR sv.governance_status = 'FAILED'),
    'runs', (SELECT coalesce(json_agg(row_to_json(run_row) ORDER BY run_row.created_at), '[]'::json) FROM (
      SELECT id, state, counters, error_summary, created_at FROM ingestion_runs
      WHERE data_source_id = '$source_id' AND workflow_id LIKE 'local-scan-%' AND created_at >= '$started_at'::timestamptz
      ORDER BY created_at DESC LIMIT 2
    ) AS run_row)
  )::text
  FROM data_sources ds
  LEFT JOIN source_assets sa ON sa.data_source_id = ds.id AND sa.current_version_id IS NOT NULL
  LEFT JOIN source_versions sv ON sv.id = sa.current_version_id
  WHERE ds.id = '$source_id'
  GROUP BY ds.id" > "$work/database.json"
chmod 600 "$work/database.json"

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
    )::text" > "$work/governance.json"
chmod 600 "$work/governance.json"

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

python3 - "$work/database.json" "$work/governance.json" "$work/search.json" "$preflight_json" "$source_id" \
  "$source_type_value" "$dataset_key" "$license_id" "$minimum_files" "$versions_after_first" "$versions_after_second" \
  "$ai_model" "$output_path" <<'PY'
from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

database_path, governance_path, search_path, preflight_text, source_id, source_type, dataset, license_id, minimum, first, second, configured_model, output_text = sys.argv[1:]
database = json.loads(Path(database_path).read_text(encoding="utf-8"))
governance = json.loads(Path(governance_path).read_text(encoding="utf-8"))
response_models = governance.pop("response_models", None)
governance["configured_model"] = configured_model
governance["configured_model_runs"] = (
    governance.get("successful_extraction_runs") if response_models == [configured_model] else 0
)
search = json.loads(Path(search_path).read_text(encoding="utf-8"))
preflight = json.loads(preflight_text)
minimum_count = int(minimum)
runs = database.get("runs")
if preflight.get("source_id") != source_id or preflight.get("source_type") != source_type:
    raise SystemExit("connector inspection was not bound to the requested source")
if preflight.get("configuration_error_count") != 0 or preflight.get("error_count") != 0:
    raise SystemExit("connector inspection reported configuration or discovery errors")
if preflight.get("oversized") != 0:
    raise SystemExit("connector inspection returned oversized source objects")
if preflight.get("discovered", 0) < minimum_count or preflight.get("stable", 0) < minimum_count:
    raise SystemExit("source inventory has insufficient stable objects for real-source acceptance")
if database.get("source_state") != "ACTIVE":
    raise SystemExit("source did not return to ACTIVE after scanning")
if not isinstance(runs, list) or len(runs) != 2:
    raise SystemExit("exactly two local ingestion runs were not recorded")
for run in runs:
    counters = run.get("counters")
    if run.get("state") != "SUCCEEDED" or run.get("error_summary") is not None or not isinstance(counters, dict):
        raise SystemExit("an ingestion acceptance run did not succeed cleanly")
    if counters.get("failed") != 0 or counters.get("unstable") != 0:
        raise SystemExit("an ingestion acceptance run contains failed or unstable files")
second_run = runs[-1]
if second_run["counters"].get("discovered") != 0:
    raise SystemExit("second ingestion scan was not idempotent")
if second_run["counters"].get("unchanged", 0) < minimum_count:
    raise SystemExit("source did not report unchanged objects on the second scan")
versions = database.get("current_versions")
if not isinstance(versions, int) or versions < minimum_count:
    raise SystemExit("ingestion did not produce the required current versions")
if database.get("assets") != versions or database.get("active_assets") != versions or database.get("traceable_versions") != versions:
    raise SystemExit("ingestion assets are not fully snapshotted and traceable")
if database.get("secure_versions") != versions:
    raise SystemExit("ingestion versions did not all pass fail-closed malware scanning")
if database.get("processed_versions") != versions or database.get("failed_versions") != 0:
    raise SystemExit("ingestion versions are not fully processed without failures")
governable = database.get("governable_versions")
if (
    not isinstance(governable, int)
    or governable < 1
    or database.get("governed_versions") != governable
    or database.get("projected_versions") != governable
):
    raise SystemExit("ingestion versions did not complete AI governance and OpenSearch projection")
if int(first) != int(second) or int(second) < minimum_count:
    raise SystemExit("ingestion version inventory changed during the idempotence scan")
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
    raise SystemExit("AI governance accounting contains invalid counters")
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
    raise SystemExit("AI governance did not produce fully accounted, quote-located facts")
cluster = search.get("cluster")
deliveries = search.get("deliveries")
if not isinstance(cluster, dict) or cluster.get("available") is not True or cluster.get("cluster_status") != "green":
    raise SystemExit("OpenSearch is unavailable after ingestion")
if not isinstance(deliveries, dict) or any(deliveries.get(name) != 0 for name in ("dead", "retry", "processing")):
    raise SystemExit("OpenSearch projection delivery queue is not drained after ingestion")
report = {
    "schema": "pharma.ingestion-pilot-evidence.v2",
    "schema_version": 2,
    "generated_at": datetime.now(UTC).isoformat(),
    "status": "passed",
    "environment": "local-wsl",
    "production_claim": False,
    "source_id": source_id,
    "source_type": source_type,
    "dataset_key": dataset,
    "license_id": license_id,
    "source_files": preflight,
    "versions": {
        "current": versions,
        "traceable": database["traceable_versions"],
        "malware_scanned": database["secure_versions"],
        "processed": database["processed_versions"],
        "governable": governable,
        "governed": database["governed_versions"],
        "projected": database["projected_versions"],
        "failed": database["failed_versions"],
        "idempotent_second_scan": True,
    },
    "governance": governance,
    "runs": [{"id": run["id"], "state": run["state"], "counters": run["counters"]} for run in runs],
    "search": {"cluster": cluster, "deliveries": deliveries},
    "source_content_created_by_test": False,
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
            raise SystemExit(f"refusing to overwrite ingestion evidence: {output}") from exc
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
  printf 'ingestion_report=%s\n' "$output_path"
fi
