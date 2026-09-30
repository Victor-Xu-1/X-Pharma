#!/usr/bin/env bash
set -Eeuo pipefail

umask 077

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$root"

output_path=""
timeout_seconds=360

while [[ $# -gt 0 ]]; do
  case "$1" in
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
    -h|--help)
      echo "Usage: verify-source-stage-replay.sh [--timeout-seconds N] [--output FILE]"
      exit 0
      ;;
    *)
      echo "unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

[[ "$timeout_seconds" =~ ^[1-9][0-9]*$ && "$timeout_seconds" -ge 60 && "$timeout_seconds" -le 3600 ]] || {
  echo "--timeout-seconds must be between 60 and 3600" >&2
  exit 2
}

for command in curl docker openssl python3 realpath; do
  command -v "$command" >/dev/null 2>&1 || { echo "required command is unavailable: $command" >&2; exit 1; }
done

export COMPOSE_FILE="${COMPOSE_FILE:-compose.yaml:compose.dev.yaml:compose.telemetry.yaml}"
worker_container=""
for service in api worker postgres temporal parser clamav opensearch; do
  container=$(docker compose ps -q "$service")
  [[ -n "$container" && "$(docker inspect --format '{{.State.Running}}' "$container")" == true ]] || {
    echo "required Compose service is not running: $service" >&2
    exit 1
  }
  [[ "$service" == worker ]] && worker_container=$container
done

knowledge_source_root=$(docker inspect --format \
  '{{range .Mounts}}{{if eq .Destination "/sources/knowledge"}}{{.Source}}{{end}}{{end}}' \
  "$worker_container")
[[ -n "$knowledge_source_root" && "$knowledge_source_root" = /* && -d "$knowledge_source_root" ]] || {
  echo "worker does not expose a valid /sources/knowledge host mount" >&2
  exit 1
}
knowledge_source_root=$(realpath "$knowledge_source_root")

base_url="${PHARMA_BASE_URL:-http://127.0.0.1:18380}"
run_id="$(date -u +%Y%m%d%H%M%S)-$RANDOM"
fixture_key="source-stage-replay-$run_id"
fixture_root="$knowledge_source_root/.$fixture_key"
fixture_file="$fixture_root/controlled-$run_id.md"
output_dir="/tmp/pharma-source-stage-replay-$$"
cookie_jar="$output_dir/cookies.txt"
mkdir -m 0700 "$output_dir"
mkdir -m 0755 "$fixture_root"
[[ "$(realpath "$fixture_root")" == "$knowledge_source_root/.$fixture_key" ]] || {
  echo "controlled fixture escaped the mounted source root" >&2
  exit 1
}
printf '%s\n' \
  "Automated pipeline health-check marker $run_id. This fixture contains no biomedical assertion." \
  > "$fixture_file"
chmod 0644 "$fixture_file"

pg_user=$(docker compose exec -T postgres printenv POSTGRES_USER | tr -d '\r')
pg_db=$(docker compose exec -T postgres printenv POSTGRES_DB | tr -d '\r')
[[ "$pg_user" =~ ^[a-z_][a-z0-9_]*$ && "$pg_db" =~ ^[a-z_][a-z0-9_]*$ ]] || {
  echo "unsafe PostgreSQL identity returned by runtime" >&2
  exit 1
}

tenant_record=$(
  docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -At -F '|' -v ON_ERROR_STOP=1 \
    -c "SELECT td.tenant_id, td.dataset_key
        FROM tenant_datasets td
        JOIN tenants t ON t.id = td.tenant_id
        WHERE t.active AND td.active
          AND (td.license_policy::jsonb)->>'schema_version' = '1.0'
          AND (td.license_policy::jsonb)->'permitted_channels' @> '[\"web\"]'::jsonb
        ORDER BY td.created_at, td.id LIMIT 1"
)
IFS='|' read -r tenant_id dataset_key <<< "$tenant_record"
[[ "$tenant_id" =~ ^[0-9a-f-]{36}$ && "$dataset_key" =~ ^[a-z][a-z0-9_-]{1,79}$ ]] || {
  echo "an active licensed dataset is required for stage replay acceptance" >&2
  exit 1
}

user_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
email="$fixture_key@example.test"
password="$(openssl rand -hex 24)Aa1!"
password_hash=$(docker compose exec -T api python -c \
  'import sys; from pharma_intel.security import hash_password; print(hash_password(sys.argv[1]))' "$password" | tr -d '\r')
[[ "$password_hash" == \$argon2* ]] || { echo "runtime returned an invalid password hash" >&2; exit 1; }

source_id=""
asset_id=""
version_id=""
raw_object_uri=""
raw_sha256=""
text_object_uri=""
text_sha256=""
object_cleanup_failures=0
cleanup_done=false

cleanup() {
  [[ "$cleanup_done" == false ]] || return 0
  cleanup_done=true

  if [[ -n "$asset_id" ]]; then
    docker compose exec -T worker python - "$tenant_id" "$asset_id" >/dev/null <<'PY' || true
import sys
from pharma_intel.search.client import get_opensearch_gateway
get_opensearch_gateway().delete_source_asset_evidence(sys.argv[1], sys.argv[2])
PY
  fi

  for record in "$raw_object_uri|$raw_sha256" "$text_object_uri|$text_sha256"; do
    IFS='|' read -r uri digest <<< "$record"
    [[ -n "$uri" && "$digest" =~ ^[0-9a-f]{64}$ ]] || continue
    if ! docker compose exec -T worker python - "$uri" "$digest" >/dev/null <<'PY'
import sys
from pharma_intel.config import get_settings
from pharma_intel.object_store import build_object_store
store = build_object_store(get_settings())
store.delete(sys.argv[1], sys.argv[2])
PY
    then
      object_cleanup_failures=$((object_cleanup_failures + 1))
    fi
  done

  if [[ -n "$source_id" ]]; then
    docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -v ON_ERROR_STOP=1 \
      -v tenant_id="$tenant_id" -v source_id="$source_id" >/dev/null <<'SQL' || true
BEGIN;
CREATE TEMP TABLE fixture_versions AS
SELECT sv.id, sv.source_document_id, sv.retrieval_projection_id
FROM source_versions sv
JOIN source_assets sa ON sa.id = sv.source_asset_id
WHERE sv.tenant_id = :'tenant_id' AND sa.data_source_id = :'source_id';
CREATE TEMP TABLE fixture_runs AS
SELECT er.id FROM extraction_runs er WHERE er.source_version_id IN (SELECT id FROM fixture_versions);
CREATE TEMP TABLE fixture_facts AS
SELECT sf.id FROM staged_facts sf WHERE sf.extraction_run_id IN (SELECT id FROM fixture_runs);
CREATE TEMP TABLE fixture_events AS
SELECT oe.id FROM outbox_events oe
WHERE oe.tenant_id = :'tenant_id'
  AND oe.aggregate_type IN ('source_version', 'source_asset')
  AND oe.aggregate_id IN (
    SELECT id FROM fixture_versions
    UNION ALL
    SELECT id FROM source_assets WHERE data_source_id = :'source_id'
  );
DELETE FROM fact_provenance_links WHERE staged_fact_id IN (SELECT id FROM fixture_facts);
DELETE FROM review_tasks WHERE staged_fact_id IN (SELECT id FROM fixture_facts);
DELETE FROM staged_facts WHERE id IN (SELECT id FROM fixture_facts);
DELETE FROM extraction_runs WHERE id IN (SELECT id FROM fixture_runs);
DELETE FROM projection_deliveries WHERE outbox_event_id IN (SELECT id FROM fixture_events);
DELETE FROM outbox_events WHERE id IN (SELECT id FROM fixture_events);
DELETE FROM source_version_operations WHERE source_version_id IN (SELECT id FROM fixture_versions);
DELETE FROM audit_events
WHERE tenant_id = :'tenant_id'
  AND (
    (resource_type = 'data_source' AND resource_id = :'source_id')
    OR (resource_type = 'source_version' AND resource_id IN (SELECT id FROM fixture_versions))
  );
DELETE FROM ingestion_findings WHERE ingestion_run_id IN (
  SELECT id FROM ingestion_runs WHERE data_source_id = :'source_id'
);
DELETE FROM ingestion_run_operations WHERE ingestion_run_id IN (
  SELECT id FROM ingestion_runs WHERE data_source_id = :'source_id'
);
DELETE FROM ingestion_runs WHERE data_source_id = :'source_id';
UPDATE source_versions SET retrieval_projection_id = NULL, source_document_id = NULL
WHERE id IN (SELECT id FROM fixture_versions);
DELETE FROM retrieval_projections WHERE id IN (
  SELECT retrieval_projection_id FROM fixture_versions WHERE retrieval_projection_id IS NOT NULL
);
DELETE FROM source_versions WHERE id IN (SELECT id FROM fixture_versions);
DELETE FROM source_assets WHERE data_source_id = :'source_id';
DELETE FROM source_documents
WHERE tenant_id = :'tenant_id' AND id IN (
  SELECT source_document_id FROM fixture_versions WHERE source_document_id IS NOT NULL
);
DELETE FROM data_sources WHERE id = :'source_id';
COMMIT;
SQL
  fi

  docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -v ON_ERROR_STOP=1 \
    -v user_id="$user_id" >/dev/null 2>&1 <<'SQL' || true
DELETE FROM users WHERE id = :'user_id';
SQL
  rm -f -- "$fixture_file"
  rmdir -- "$fixture_root" 2>/dev/null || true
  rm -rf -- "$output_dir"
}
trap cleanup EXIT INT TERM

docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -v ON_ERROR_STOP=1 \
  -v user_id="$user_id" -v tenant_id="$tenant_id" -v email="$email" -v password_hash="$password_hash" \
  >/dev/null <<'SQL'
INSERT INTO users (
  id, tenant_id, email, normalized_email, display_name, password_hash,
  role, active, token_version, created_at, updated_at
) VALUES (
  :'user_id', :'tenant_id', :'email', :'email', 'Stage replay acceptance',
  :'password_hash', 'ADMIN', true, 1, now(), now()
);
SQL

login_status=$(curl -sS -o "$output_dir/login.json" -w '%{http_code}' \
  -c "$cookie_jar" -H 'Content-Type: application/json' \
  --data "$(python3 -c 'import json,sys; print(json.dumps({"email":sys.argv[1],"password":sys.argv[2]}))' "$email" "$password")" \
  "$base_url/api/v1/auth/login")
[[ "$login_status" == 200 ]] || { echo "fixture login failed with HTTP $login_status" >&2; exit 1; }
csrf_token=$(awk '$6 == "pharma_csrf" {print $7}' "$cookie_jar")
[[ -n "$csrf_token" ]] || { echo "fixture login did not return a CSRF token" >&2; exit 1; }
unset password password_hash

python3 - "$output_dir/source-create.json" "$fixture_key" "$dataset_key" <<'PY'
import json
import sys
path, fixture_key, dataset_key = sys.argv[1:]
json.dump({
    "name": f"Stage replay acceptance {fixture_key}",
    "source_type": "folder",
    "root_uri": f"/sources/knowledge/.{fixture_key}",
    "owner": "Data Operations Acceptance",
    "data_classification": "internal",
    "authorization_scopes": ["contract:source-stage-replay-acceptance"],
    "dataset_key": dataset_key,
    "include_globs": ["*", "**/*"],
    "exclude_globs": [],
    "stable_seconds": 0,
    "max_file_bytes": 1048576,
    "scan_interval_seconds": 86400,
    "expected_freshness_seconds": 86400,
    "rate_limit_per_minute": 60,
}, open(path, "w", encoding="utf-8"), separators=(",", ":"))
PY
create_status=$(curl -sS -o "$output_dir/source.json" -w '%{http_code}' \
  -b "$cookie_jar" -H "X-CSRF-Token: $csrf_token" -H 'Content-Type: application/json' \
  --data-binary "@$output_dir/source-create.json" "$base_url/api/v1/admin/data-sources")
[[ "$create_status" == 201 ]] || { echo "source creation failed with HTTP $create_status" >&2; exit 1; }
source_id=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["id"])' "$output_dir/source.json")
[[ "$source_id" =~ ^[0-9a-f-]{36}$ ]] || { echo "invalid source identifier" >&2; exit 1; }

# Prevent the scheduler from racing this controlled one-shot ingestion.
docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -v ON_ERROR_STOP=1 \
  -v source_id="$source_id" >/dev/null <<'SQL'
UPDATE data_sources SET last_scanned_at=now(), last_success_at=now() WHERE id=:'source_id';
SQL

docker compose exec -T worker pharma-ingest once --source-id "$source_id" >"$output_dir/initial-ingestion.log" 2>&1 || {
  echo "initial real ingestion failed" >&2
  sed -n '1,160p' "$output_dir/initial-ingestion.log" >&2
  exit 1
}

asset_id=$(curl -fsS -b "$cookie_jar" \
  "$base_url/api/v1/admin/source-assets?data_source_id=$source_id&limit=10&offset=0" | \
  python3 -c 'import json,sys; p=json.load(sys.stdin); assert p["total"]==1; print(p["items"][0]["id"])')
[[ "$asset_id" =~ ^[0-9a-f-]{36}$ ]] || { echo "invalid source asset identifier" >&2; exit 1; }

deadline=$((SECONDS + timeout_seconds))
while (( SECONDS < deadline )); do
  curl -fsS -b "$cookie_jar" "$base_url/api/v1/admin/source-assets/$asset_id" > "$output_dir/detail-initial.json"
  IFS='|' read -r version_id parse_status retrieval_status governance_status current_state current_error < <(
    python3 - "$output_dir/detail-initial.json" <<'PY'
import json, sys
v=json.load(open(sys.argv[1], encoding="utf-8"))["versions"][0]
print("|".join((v["id"],v["parse_status"],v["retrieval_status"],v["governance_status"],v["state"],v["error_code"] or "")))
PY
  )
  [[ "$parse_status|$retrieval_status|$governance_status|$current_error" == "succeeded|succeeded|succeeded|" ]] && break
  sleep 2
done
[[ "$parse_status|$retrieval_status|$governance_status|$current_error" == "succeeded|succeeded|succeeded|" ]] || {
  echo "initial real ingestion did not finish: state=$current_state error=$current_error" >&2
  exit 1
}

IFS='|' read -r raw_object_uri raw_sha256 text_object_uri text_sha256 fact_count < <(
  docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -At -F '|' -v ON_ERROR_STOP=1 \
    -v version_id="$version_id" <<'SQL'
SELECT sv.raw_object_uri, sv.content_sha256, sv.extracted_text_object_uri, sv.extracted_text_sha256,
       (SELECT count(*) FROM staged_facts sf JOIN extraction_runs er ON er.id=sf.extraction_run_id
        WHERE er.source_version_id=sv.id)
FROM source_versions sv WHERE sv.id=:'version_id';
SQL
)
[[ "$raw_object_uri" == file://* && "$raw_sha256" =~ ^[0-9a-f]{64}$ && \
   "$text_object_uri" == file://* && "$text_sha256" =~ ^[0-9a-f]{64}$ && "$fact_count" == 0 ]] || {
  echo "fixture did not produce an isolated zero-fact governed version" >&2
  exit 1
}

submit_replay() {
  local stage=$1 expected_state=$2 expected_error=$3 operation_key=$4 reason=$5 response_path=$6
  python3 - "$output_dir/replay-request.json" "$stage" "$expected_state" "$expected_error" "$operation_key" "$reason" <<'PY'
import json, sys
path, stage, state, error, key, reason = sys.argv[1:]
payload={"operation_key":key,"expected_state":state,"expected_error_code":error or None,"from_stage":stage,"reason":reason}
json.dump(payload, open(path,"w",encoding="utf-8"), separators=(",",":"))
PY
  local status_code
  status_code=$(curl -sS -o "$response_path" -w '%{http_code}' -b "$cookie_jar" \
    -H "X-CSRF-Token: $csrf_token" -H 'Content-Type: application/json' \
    --data-binary "@$output_dir/replay-request.json" \
    "$base_url/api/v1/admin/source-versions/$version_id/replay")
  [[ "$status_code" == 202 ]] || {
    echo "$stage replay failed with HTTP $status_code" >&2
    python3 -c 'import json,sys; print(json.dumps(json.load(open(sys.argv[1])),ensure_ascii=True))' "$response_path" >&2 || true
    return 1
  }
  [[ "$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["from_stage"])' "$response_path")" == "$stage" ]]
}

wait_for_recovery() {
  local stage=$1
  local limit=$((SECONDS + timeout_seconds))
  while (( SECONDS < limit )); do
    curl -fsS -b "$cookie_jar" "$base_url/api/v1/admin/source-assets/$asset_id" > "$output_dir/detail-$stage.json"
    IFS='|' read -r parse_status retrieval_status governance_status current_state current_error < <(
      python3 - "$output_dir/detail-$stage.json" "$version_id" <<'PY'
import json, sys
v=next(v for v in json.load(open(sys.argv[1],encoding="utf-8"))["versions"] if v["id"]==sys.argv[2])
print("|".join((v["parse_status"],v["retrieval_status"],v["governance_status"],v["state"],v["error_code"] or "")))
PY
    )
    [[ "$parse_status|$retrieval_status|$governance_status|$current_error" == "succeeded|succeeded|succeeded|" ]] && return 0
    sleep 2
  done
  echo "$stage recovery timed out: state=$current_state error=$current_error" >&2
  return 1
}

# Parse recovery reuses the immutable snapshot and the prior successful malware scan.
docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -v ON_ERROR_STOP=1 \
  -v version_id="$version_id" >/dev/null <<'SQL'
UPDATE source_versions SET state='FAILED', parse_status='FAILED', retrieval_status='NOT_STARTED',
  governance_status='NOT_STARTED', error_code='parse_failed', error_message='controlled parser failure'
WHERE id=:'version_id';
SQL
parse_key="stage-replay:parse:$run_id"
submit_replay parse failed parse_failed "$parse_key" "Controlled parse-stage recovery" "$output_dir/replay-parse.json"
wait_for_recovery parse

# The same idempotency key must return exactly the accepted command after state advancement.
submit_replay parse failed parse_failed "$parse_key" "Controlled parse-stage recovery" "$output_dir/replay-parse-duplicate.json"
cmp -s "$output_dir/replay-parse.json" "$output_dir/replay-parse-duplicate.json" || {
  echo "parse replay idempotency response drifted" >&2
  exit 1
}

# Governance recovery must restore the source-version state from the durable successful extraction run.
docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -v ON_ERROR_STOP=1 \
  -v version_id="$version_id" >/dev/null <<'SQL'
UPDATE source_versions SET state='GOVERNANCE_PENDING', governance_status='FAILED', retrieval_status='NOT_STARTED',
  error_code='governance_model_failed', error_message='controlled provider failure'
WHERE id=:'version_id';
SQL
submit_replay governance governance_pending governance_model_failed "stage-replay:governance:$run_id" \
  "Controlled governance-stage recovery" "$output_dir/replay-governance.json"
wait_for_recovery governance

# Projection failures have no source-version error code; the failed stage itself is the optimistic guard.
current_state=$(python3 - "$output_dir/detail-governance.json" <<'PY'
import json, sys
print(json.load(open(sys.argv[1],encoding="utf-8"))["versions"][0]["state"])
PY
)
docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -v ON_ERROR_STOP=1 \
  -v version_id="$version_id" >/dev/null <<'SQL'
UPDATE source_versions SET retrieval_status='FAILED', error_code=NULL, error_message=NULL
WHERE id=:'version_id';
SQL
submit_replay retrieval "$current_state" "" "stage-replay:retrieval:$run_id" \
  "Controlled retrieval-stage recovery" "$output_dir/replay-retrieval.json"
wait_for_recovery retrieval

operation_audit=$(docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -At -F '|' -v ON_ERROR_STOP=1 \
  -v tenant_id="$tenant_id" -v version_id="$version_id" <<'SQL'
SELECT
  (SELECT count(*) FROM source_version_operations
   WHERE tenant_id=:'tenant_id' AND source_version_id=:'version_id' AND state='accepted'),
  (SELECT count(*) FROM audit_events
   WHERE tenant_id=:'tenant_id' AND resource_type='source_version' AND resource_id=:'version_id'
     AND action='source_version.replay' AND outcome='success'),
  (SELECT count(*) FROM extraction_runs WHERE source_version_id=:'version_id' AND status='SUCCEEDED');
SQL
)
[[ "$operation_audit" == "3|3|1" ]] || { echo "stage replay evidence is incomplete: $operation_audit" >&2; exit 1; }

workflow_id="source-version-reprocess-$version_id"
workflow_status=$(docker compose exec -T temporal tctl --address temporal:7233 workflow describe \
  --workflow_id "$workflow_id" 2>/dev/null | python3 -c \
  'import json,sys; print(json.load(sys.stdin)["workflowExecutionInfo"]["status"])')
[[ "$workflow_status" == Completed ]] || { echo "latest stage replay workflow is not completed" >&2; exit 1; }

finished_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
cleanup
trap - EXIT INT TERM

remaining=$(docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -At -F '|' -v ON_ERROR_STOP=1 \
  -v source_id="$source_id" -v user_id="$user_id" -v version_id="$version_id" <<'SQL'
SELECT (SELECT count(*) FROM data_sources WHERE id=:'source_id'),
       (SELECT count(*) FROM users WHERE id=:'user_id'),
       (SELECT count(*) FROM source_versions WHERE id=:'version_id');
SQL
)
[[ "$remaining" == "0|0|0" && "$object_cleanup_failures" == 0 && ! -e "$fixture_file" ]] || {
  echo "stage replay fixture cleanup failed: db=$remaining objects=$object_cleanup_failures" >&2
  exit 1
}

report=$(python3 - "$finished_at" "$timeout_seconds" <<'PY'
import json, sys
print(json.dumps({
  "schema":"pharma.source-stage-replay-acceptance.v1",
  "status":"passed",
  "finished_at":sys.argv[1],
  "timeout_seconds":int(sys.argv[2]),
  "stages":{"parse":"passed","governance":"passed","retrieval":"passed"},
  "path":{"real_markdown":"passed","http_api":"passed","postgresql":"passed","temporal":"passed",
          "worker":"passed","parser":"passed","third_party_llm_api":"passed","transactional_outbox":"passed",
          "opensearch":"passed","immutable_object_store":"passed"},
  "idempotency":"passed","audit":"passed","credentials_recorded":False,
  "temporary_database_records_after":0,"temporary_source_files_after":0,"temporary_objects_after":0,
},sort_keys=True,separators=(",",":")))
PY
)

if [[ -n "$output_path" ]]; then
  output_parent=$(dirname "$output_path")
  mkdir -p "$output_parent"
  output_parent=$(realpath "$output_parent")
  output_name=$(basename "$output_path")
  [[ "$output_name" != */* && "$output_name" != . && "$output_name" != .. ]] || exit 2
  temporary_report=$(mktemp "$output_parent/.${output_name}.XXXXXX")
  chmod 0600 "$temporary_report"
  printf '%s\n' "$report" > "$temporary_report"
  mv -f -- "$temporary_report" "$output_parent/$output_name"
fi
printf '%s\n' "$report"
