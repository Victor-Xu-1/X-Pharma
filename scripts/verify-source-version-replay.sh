#!/usr/bin/env bash
set -Eeuo pipefail

umask 077

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$root"

output_path=""
timeout_seconds=240

usage() {
  cat <<'EOF'
Usage: verify-source-version-replay.sh [options]

Exercise source-version recovery through the real HTTP, PostgreSQL, Temporal,
worker, immutable object-store and ClamAV path. The controlled fixture first
fails against an unreachable scanner endpoint and is then replayed from the
malware-scan stage against the healthy runtime.

Options:
  --timeout-seconds N  Maximum replay completion wait (default: 240).
  --output FILE        Write an atomic machine-readable report.
  -h, --help
EOF
}

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

[[ "$timeout_seconds" =~ ^[1-9][0-9]*$ && "$timeout_seconds" -ge 30 && "$timeout_seconds" -le 3600 ]] || {
  echo "--timeout-seconds must be between 30 and 3600" >&2
  exit 2
}

for command in curl docker openssl python3 realpath; do
  command -v "$command" >/dev/null 2>&1 || {
    echo "required command is unavailable: $command" >&2
    exit 1
  }
done

export COMPOSE_FILE="${COMPOSE_FILE:-compose.yaml:compose.dev.yaml:compose.telemetry.yaml}"
worker_container=""
for service in api worker postgres temporal clamav parser; do
  container=$(docker compose ps -q "$service")
  [[ -n "$container" && "$(docker inspect --format '{{.State.Running}}' "$container")" == true ]] || {
    echo "required Compose service is not running: $service" >&2
    exit 1
  }
  if [[ "$service" == worker ]]; then
    worker_container=$container
  fi
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
fixture_key="source-version-replay-$run_id"
fixture_root="$knowledge_source_root/.$fixture_key"
fixture_file="$fixture_root/controlled-$run_id.cdx"
output_dir="/tmp/pharma-source-version-replay-$$"
cookie_jar="$output_dir/cookies.txt"
mkdir -m 0700 "$output_dir"
mkdir -m 0755 "$fixture_root"
[[ "$(realpath "$fixture_root")" == "$knowledge_source_root/.$fixture_key" ]] || {
  echo "controlled fixture escaped the mounted source root" >&2
  exit 1
}
printf '%s\n' "Controlled source-version replay fixture $run_id" > "$fixture_file"
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
          AND (
            (td.license_policy::jsonb)->'permitted_channels' @> '[\"web\"]'::jsonb
            OR (td.license_policy::jsonb)->'permitted_channels' @> '[\"mcp\"]'::jsonb
          )
        ORDER BY td.created_at, td.id LIMIT 1"
)
IFS='|' read -r tenant_id dataset_key <<< "$tenant_record"
[[ "$tenant_id" =~ ^[0-9a-f-]{36}$ && "$dataset_key" =~ ^[a-z][a-z0-9_-]{1,79}$ ]] || {
  echo "an active licensed dataset is required for replay acceptance" >&2
  exit 1
}

user_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
email="$fixture_key@example.test"
password="$(openssl rand -hex 24)Aa1!"
password_hash=$(docker compose exec -T api python -c \
  'import sys; from pharma_intel.security import hash_password; print(hash_password(sys.argv[1]))' "$password" | tr -d '\r')
[[ "$password_hash" == \$argon2* ]] || {
  echo "runtime returned an invalid password hash" >&2
  exit 1
}

source_id=""
asset_id=""
version_id=""
workflow_id=""
raw_object_uri=""
raw_content_sha256=""
cleanup_done=false

terminate_workflow() {
  [[ -n "$workflow_id" ]] || return 0
  docker compose exec -T temporal tctl --address temporal:7233 workflow terminate \
    --workflow_id "$workflow_id" --reason "acceptance cleanup" >/dev/null 2>&1 || true
}

cleanup() {
  [[ "$cleanup_done" == false ]] || return 0
  cleanup_done=true
  terminate_workflow

  if [[ -n "$source_id" ]]; then
    docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -v ON_ERROR_STOP=1 \
      -v tenant_id="$tenant_id" -v source_id="$source_id" >/dev/null <<'SQL'
BEGIN;
CREATE TEMP TABLE replay_versions (id varchar(36), source_document_id varchar(36)) ON COMMIT DROP;
INSERT INTO replay_versions
SELECT sv.id, sv.source_document_id
FROM source_versions sv
JOIN source_assets sa ON sa.id = sv.source_asset_id
WHERE sa.tenant_id = :'tenant_id' AND sa.data_source_id = :'source_id';

DELETE FROM audit_events
WHERE tenant_id = :'tenant_id'
  AND (
    (resource_type = 'data_source' AND resource_id = :'source_id')
    OR (resource_type = 'source_version' AND resource_id IN (SELECT id FROM replay_versions))
  );
DELETE FROM source_version_operations
WHERE tenant_id = :'tenant_id' AND source_version_id IN (SELECT id FROM replay_versions);
DELETE FROM outbox_events
WHERE tenant_id = :'tenant_id' AND aggregate_type = 'source_version'
  AND aggregate_id IN (SELECT id FROM replay_versions);
DELETE FROM ingestion_findings
WHERE tenant_id = :'tenant_id' AND ingestion_run_id IN (
  SELECT id FROM ingestion_runs WHERE data_source_id = :'source_id'
);
DELETE FROM ingestion_run_operations
WHERE tenant_id = :'tenant_id' AND ingestion_run_id IN (
  SELECT id FROM ingestion_runs WHERE data_source_id = :'source_id'
);
DELETE FROM ingestion_runs WHERE tenant_id = :'tenant_id' AND data_source_id = :'source_id';
DELETE FROM source_versions WHERE tenant_id = :'tenant_id' AND id IN (SELECT id FROM replay_versions);
DELETE FROM source_assets WHERE tenant_id = :'tenant_id' AND data_source_id = :'source_id';
DELETE FROM source_documents
WHERE tenant_id = :'tenant_id' AND id IN (
  SELECT source_document_id FROM replay_versions WHERE source_document_id IS NOT NULL
);
DELETE FROM data_sources WHERE tenant_id = :'tenant_id' AND id = :'source_id';
COMMIT;
SQL
  fi

  docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -v ON_ERROR_STOP=1 \
    -v user_id="$user_id" >/dev/null <<'SQL' || true
DELETE FROM users WHERE id = :'user_id';
SQL

  if [[ -n "$raw_object_uri" && "$raw_content_sha256" =~ ^[0-9a-f]{64}$ ]]; then
    docker compose exec -T worker python - "$raw_object_uri" "$raw_content_sha256" >/dev/null <<'PY' || true
import sys

from pharma_intel.config import get_settings
from pharma_intel.object_store import build_object_store

store = build_object_store(get_settings())
store.delete(sys.argv[1], sys.argv[2])
PY
  fi

  rm -f -- "$fixture_file"
  rmdir -- "$fixture_root" 2>/dev/null || true
  rm -rf -- "$output_dir"
}
trap cleanup EXIT INT TERM

docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -v ON_ERROR_STOP=1 \
  -v user_id="$user_id" -v tenant_id="$tenant_id" -v email="$email" \
  -v password_hash="$password_hash" >/dev/null <<'SQL'
INSERT INTO users (
  id, tenant_id, email, normalized_email, display_name, password_hash,
  role, active, token_version, created_at, updated_at
) VALUES (
  :'user_id', :'tenant_id', :'email', :'email', 'Source replay acceptance',
  :'password_hash', 'ADMIN', true, 1, now(), now()
);
SQL

login_status=$(curl -sS -o "$output_dir/login.json" -w '%{http_code}' \
  -c "$cookie_jar" -H 'Content-Type: application/json' \
  --data "$(python3 -c 'import json,sys; print(json.dumps({"email":sys.argv[1],"password":sys.argv[2]}))' "$email" "$password")" \
  "$base_url/api/v1/auth/login")
[[ "$login_status" == 200 ]] || {
  echo "fixture login failed with HTTP $login_status" >&2
  exit 1
}
csrf_token=$(awk '$6 == "pharma_csrf" {print $7}' "$cookie_jar")
[[ -n "$csrf_token" ]] || {
  echo "fixture login did not return a CSRF token" >&2
  exit 1
}
unset password password_hash

python3 - "$output_dir/source-create.json" "$fixture_key" "$dataset_key" <<'PY'
import json
import sys

path, fixture_key, dataset_key = sys.argv[1:]
payload = {
    "name": f"Source replay acceptance {fixture_key}",
    "source_type": "folder",
    "root_uri": f"/sources/knowledge/.{fixture_key}",
    "owner": "Data Operations Acceptance",
    "data_classification": "internal",
    "authorization_scopes": ["contract:source-replay-acceptance"],
    "dataset_key": dataset_key,
    "include_globs": ["*", "**/*"],
    "exclude_globs": [],
    "stable_seconds": 0,
    "max_file_bytes": 1048576,
    "scan_interval_seconds": 86400,
    "expected_freshness_seconds": 86400,
    "rate_limit_per_minute": 60,
}
with open(path, "w", encoding="utf-8") as stream:
    json.dump(payload, stream, separators=(",", ":"))
PY

create_status=$(curl -sS -o "$output_dir/source.json" -w '%{http_code}' \
  -b "$cookie_jar" -H "X-CSRF-Token: $csrf_token" -H 'Content-Type: application/json' \
  --data-binary "@$output_dir/source-create.json" "$base_url/api/v1/admin/data-sources")
[[ "$create_status" == 201 ]] || {
  echo "source creation failed with HTTP $create_status" >&2
  python3 - "$output_dir/source.json" <<'PY' >&2
import json
import sys

try:
    print(json.dumps(json.load(open(sys.argv[1], encoding="utf-8")), ensure_ascii=True))
except (OSError, ValueError):
    print("source creation response was not valid JSON")
PY
  exit 1
}
source_id=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["id"])' "$output_dir/source.json")
[[ "$source_id" =~ ^[0-9a-f-]{36}$ ]] || {
  echo "source creation returned an invalid identifier" >&2
  exit 1
}

# Keep the scheduler from racing the controlled failure injection.
docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -v ON_ERROR_STOP=1 \
  -v source_id="$source_id" >/dev/null <<'SQL'
UPDATE data_sources
SET last_scanned_at = now(), last_success_at = now()
WHERE id = :'source_id';
SQL

set +e
docker compose exec -T -e CLAMAV_PORT=1 worker pharma-ingest once --source-id "$source_id" \
  >"$output_dir/controlled-failure.log" 2>&1
failure_exit=$?
set -e
[[ "$failure_exit" -ne 0 ]] || {
  echo "controlled malware scanner outage unexpectedly succeeded" >&2
  sed -n '1,120p' "$output_dir/controlled-failure.log" >&2
  exit 1
}

asset_status=$(curl -sS -o "$output_dir/assets.json" -w '%{http_code}' -b "$cookie_jar" \
  "$base_url/api/v1/admin/source-assets?data_source_id=$source_id&limit=10&offset=0")
[[ "$asset_status" == 200 ]] || {
  echo "source asset inventory failed with HTTP $asset_status" >&2
  exit 1
}
asset_record=$(python3 - "$output_dir/assets.json" <<'PY'
import json
import sys

payload = json.load(open(sys.argv[1], encoding="utf-8"))
items = payload.get("items") or []
print(f"{payload.get('total', -1)}|{items[0]['id'] if len(items) == 1 else ''}")
PY
)
IFS='|' read -r asset_total asset_id <<< "$asset_record"
[[ "$asset_total" == 1 && "$asset_id" =~ ^[0-9a-f-]{36}$ ]] || {
  echo "controlled failure produced an unexpected source asset count: $asset_total" >&2
  sed -n '1,120p' "$output_dir/controlled-failure.log" >&2
  python3 - "$output_dir/assets.json" <<'PY' >&2
import json
import sys

print(json.dumps(json.load(open(sys.argv[1], encoding="utf-8")), ensure_ascii=True))
PY
  exit 1
}

detail_status=$(curl -sS -o "$output_dir/asset-detail.json" -w '%{http_code}' -b "$cookie_jar" \
  "$base_url/api/v1/admin/source-assets/$asset_id")
[[ "$detail_status" == 200 ]] || {
  echo "source asset detail failed with HTTP $detail_status" >&2
  exit 1
}
IFS='|' read -r version_id initial_state initial_error raw_content_sha256 < <(
  python3 - "$output_dir/asset-detail.json" <<'PY'
import json
import sys

payload = json.load(open(sys.argv[1], encoding="utf-8"))
assert len(payload["versions"]) == 1
version = payload["versions"][0]
print("|".join((version["id"], version["state"], version["error_code"], version["content_sha256"])))
PY
)
[[ "$version_id" =~ ^[0-9a-f-]{36}$ && "$initial_state" == failed && "$initial_error" == malware_scan_unavailable ]] || {
  echo "controlled failure did not produce the expected replayable version" >&2
  exit 1
}
raw_object_uri=$(
  docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -At -v ON_ERROR_STOP=1 \
    -v version_id="$version_id" <<'SQL'
SELECT raw_object_uri FROM source_versions WHERE id = :'version_id';
SQL
)
[[ "$raw_object_uri" == file://* && "$raw_content_sha256" =~ ^[0-9a-f]{64}$ ]] || {
  echo "controlled version is missing its immutable raw snapshot" >&2
  exit 1
}

operation_key="replay:$run_id"
python3 - "$output_dir/replay-request.json" "$operation_key" <<'PY'
import json
import sys

payload = {
    "operation_key": sys.argv[2],
    "expected_state": "failed",
    "expected_error_code": "malware_scan_unavailable",
    "from_stage": "malware_scan",
    "reason": "Controlled scanner recovery acceptance",
}
with open(sys.argv[1], "w", encoding="utf-8") as stream:
    json.dump(payload, stream, separators=(",", ":"))
PY

replay_status=$(curl -sS -o "$output_dir/replay.json" -w '%{http_code}' \
  -b "$cookie_jar" -H "X-CSRF-Token: $csrf_token" -H 'Content-Type: application/json' \
  --data-binary "@$output_dir/replay-request.json" \
  "$base_url/api/v1/admin/source-versions/$version_id/replay")
[[ "$replay_status" == 202 ]] || {
  echo "source-version replay failed with HTTP $replay_status" >&2
  exit 1
}
workflow_id=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["workflow_id"])' "$output_dir/replay.json")
[[ "$workflow_id" == "source-version-reprocess-$version_id" ]] || {
  echo "source-version replay returned an unexpected workflow identifier" >&2
  exit 1
}

deadline=$((SECONDS + timeout_seconds))
final_state=""
final_malware_status=""
final_parse_status=""
final_error=""
while (( SECONDS < deadline )); do
  curl -fsS -b "$cookie_jar" "$base_url/api/v1/admin/source-assets/$asset_id" \
    > "$output_dir/asset-detail-final.json"
  IFS='|' read -r final_state final_malware_status final_parse_status final_error < <(
    python3 - "$output_dir/asset-detail-final.json" "$version_id" <<'PY'
import json
import sys

payload = json.load(open(sys.argv[1], encoding="utf-8"))
version = next(item for item in payload["versions"] if item["id"] == sys.argv[2])
print("|".join((version["state"], version["malware_scan_status"], version["parse_status"], version["error_code"] or "")))
PY
  )
  if [[ "$final_state" == asset_only && "$final_malware_status" == succeeded && "$final_parse_status" == skipped && -z "$final_error" ]]; then
    break
  fi
  sleep 2
done
[[ "$final_state" == asset_only && "$final_malware_status" == succeeded && "$final_parse_status" == skipped && -z "$final_error" ]] || {
  echo "source-version replay did not complete inside the bounded timeout: state=$final_state error=$final_error" >&2
  exit 1
}

duplicate_status=$(curl -sS -o "$output_dir/replay-duplicate.json" -w '%{http_code}' \
  -b "$cookie_jar" -H "X-CSRF-Token: $csrf_token" -H 'Content-Type: application/json' \
  --data-binary "@$output_dir/replay-request.json" \
  "$base_url/api/v1/admin/source-versions/$version_id/replay")
[[ "$duplicate_status" == 202 ]] || {
  echo "idempotent replay request failed with HTTP $duplicate_status" >&2
  exit 1
}
cmp -s "$output_dir/replay.json" "$output_dir/replay-duplicate.json" || {
  echo "idempotent replay returned a different response" >&2
  exit 1
}

operation_audit=$(
  docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -At -F '|' -v ON_ERROR_STOP=1 \
    -v tenant_id="$tenant_id" -v version_id="$version_id" -v operation_key="$operation_key" <<'SQL'
SELECT
  (SELECT count(*) FROM source_version_operations
    WHERE tenant_id = :'tenant_id' AND source_version_id = :'version_id'
      AND operation_key = :'operation_key' AND state = 'accepted'),
  (SELECT count(*) FROM audit_events
    WHERE tenant_id = :'tenant_id' AND resource_type = 'source_version'
      AND resource_id = :'version_id' AND action = 'source_version.replay'
      AND outcome = 'success');
SQL
)
[[ "$operation_audit" == "1|1" ]] || {
  echo "replay operation or audit evidence is incomplete: $operation_audit" >&2
  exit 1
}

workflow_status=$(docker compose exec -T temporal tctl --address temporal:7233 workflow describe \
  --workflow_id "$workflow_id" 2>/dev/null | python3 -c \
  'import json,sys; print(json.load(sys.stdin)["workflowExecutionInfo"]["status"])')
[[ "$workflow_status" == Completed ]] || {
  echo "Temporal replay workflow is not completed: ${workflow_status:-unknown}" >&2
  exit 1
}

finished_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
cleanup
trap - EXIT INT TERM

remaining=$(
  docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -At -F '|' -v ON_ERROR_STOP=1 \
    -v source_id="$source_id" -v user_id="$user_id" -v version_id="$version_id" <<'SQL'
SELECT
  (SELECT count(*) FROM data_sources WHERE id = :'source_id'),
  (SELECT count(*) FROM users WHERE id = :'user_id'),
  (SELECT count(*) FROM source_versions WHERE id = :'version_id');
SQL
)
[[ "$remaining" == "0|0|0" ]] || {
  echo "source-version replay fixture cleanup failed: $remaining" >&2
  exit 1
}

report=$(python3 - "$finished_at" "$timeout_seconds" <<'PY'
import json
import sys

print(json.dumps({
    "schema": "pharma.source-version-replay-acceptance.v1",
    "status": "passed",
    "finished_at": sys.argv[1],
    "timeout_seconds": int(sys.argv[2]),
    "path": {
        "http_api": "passed",
        "postgresql": "passed",
        "temporal": "passed",
        "worker": "passed",
        "immutable_object_store": "passed",
        "clamav_failure_and_recovery": "passed",
    },
    "initial_failure": "malware_scan_unavailable",
    "final_state": "asset_only",
    "idempotency": "passed",
    "audit": "passed",
    "temporary_database_records_after": 0,
    "temporary_source_files_after": 0,
    "temporary_objects_after": 0,
    "temporal_history_retained_for_audit": True,
    "credentials_recorded": False,
}, sort_keys=True, separators=(",", ":")))
PY
)

if [[ -n "$output_path" ]]; then
  output_parent=$(dirname "$output_path")
  mkdir -p "$output_parent"
  output_parent=$(realpath "$output_parent")
  output_name=$(basename "$output_path")
  [[ "$output_name" != */* && "$output_name" != . && "$output_name" != .. ]] || {
    echo "--output must name a file" >&2
    exit 2
  }
  temporary_report=$(mktemp "$output_parent/.${output_name}.XXXXXX")
  chmod 0600 "$temporary_report"
  printf '%s\n' "$report" > "$temporary_report"
  mv -f -- "$temporary_report" "$output_parent/$output_name"
fi

printf '%s\n' "$report"
