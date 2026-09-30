#!/usr/bin/env bash
set -Eeuo pipefail

umask 077

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$root"

output_path=""
timeout_seconds=240
file_count=1200

usage() {
  cat <<'EOF'
Usage: verify-ingestion-cancellation.sh [options]

Exercise controlled ingestion cancellation through the real HTTP, PostgreSQL,
Temporal, worker and immutable object-store path. The fixture uses many small
real files so cancellation is observed while the source workflow is active.

Options:
  --timeout-seconds N  Maximum completion wait (default: 240).
  --file-count N       Number of controlled source files (default: 1200).
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
    --file-count)
      [[ $# -ge 2 ]] || { echo "--file-count requires a value" >&2; exit 2; }
      file_count=$2
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
[[ "$file_count" =~ ^[1-9][0-9]*$ && "$file_count" -ge 200 && "$file_count" -le 5000 ]] || {
  echo "--file-count must be between 200 and 5000" >&2
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
fixture_key="ingestion-cancel-$run_id"
fixture_root="$knowledge_source_root/.$fixture_key"
output_dir="/tmp/pharma-ingestion-cancel-$$"
cookie_jar="$output_dir/cookies.txt"
mkdir -m 0700 "$output_dir"
mkdir -m 0755 "$fixture_root"
[[ "$(realpath "$fixture_root")" == "$knowledge_source_root/.$fixture_key" ]] || {
  echo "controlled fixture escaped the mounted source root" >&2
  exit 1
}
for ((index=1; index<=file_count; index++)); do
  printf 'Controlled cancellation record %06d %s\n' "$index" "$run_id" > \
    "$fixture_root/record-$(printf '%06d' "$index").md"
done
chmod -R u=rwX,go=rX "$fixture_root"

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
  echo "an active licensed dataset is required for cancellation acceptance" >&2
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
ingestion_run_id=""
temporal_workflow_id=""
temporal_run_id=""
cleanup_done=false
temporary_objects_after=0

cleanup() {
  [[ "$cleanup_done" == false ]] || return 0
  cleanup_done=true

  if [[ -n "$source_id" ]]; then
    object_records=$(docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -At -F '|' \
      -v ON_ERROR_STOP=1 -v tenant_id="$tenant_id" -v source_id="$source_id" <<'SQL' || true
SELECT sv.raw_object_uri, sv.content_sha256
FROM source_versions sv
JOIN source_assets sa ON sa.id = sv.source_asset_id
WHERE sa.tenant_id = :'tenant_id' AND sa.data_source_id = :'source_id'
  AND sv.raw_object_uri IS NOT NULL;
SQL
)
    while IFS='|' read -r object_uri object_sha; do
      [[ -n "$object_uri" && "$object_sha" =~ ^[0-9a-f]{64}$ ]] || continue
      if ! docker compose exec -T worker python - "$object_uri" "$object_sha" >/dev/null <<'PY'
import sys

from pharma_intel.config import get_settings
from pharma_intel.object_store import build_object_store

build_object_store(get_settings()).delete(sys.argv[1], sys.argv[2])
PY
      then
        temporary_objects_after=$((temporary_objects_after + 1))
      fi
    done <<< "$object_records"

    docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -v ON_ERROR_STOP=1 \
      -v tenant_id="$tenant_id" -v source_id="$source_id" >/dev/null <<'SQL'
BEGIN;
DELETE FROM audit_events
WHERE tenant_id = :'tenant_id'
  AND ((resource_type = 'data_source' AND resource_id = :'source_id')
    OR (resource_type = 'ingestion_run' AND resource_id IN (
      SELECT id FROM ingestion_runs WHERE data_source_id = :'source_id'
    )));
DELETE FROM outbox_events
WHERE tenant_id = :'tenant_id' AND aggregate_type = 'source_version'
  AND aggregate_id IN (
    SELECT sv.id FROM source_versions sv
    JOIN source_assets sa ON sa.id = sv.source_asset_id
    WHERE sa.data_source_id = :'source_id'
  );
DELETE FROM ingestion_findings WHERE ingestion_run_id IN (
  SELECT id FROM ingestion_runs WHERE data_source_id = :'source_id'
);
DELETE FROM ingestion_run_operations WHERE ingestion_run_id IN (
  SELECT id FROM ingestion_runs WHERE data_source_id = :'source_id'
);
DELETE FROM ingestion_runs WHERE tenant_id = :'tenant_id' AND data_source_id = :'source_id';
UPDATE source_assets SET current_version_id = NULL WHERE tenant_id = :'tenant_id' AND data_source_id = :'source_id';
DELETE FROM source_versions WHERE source_asset_id IN (
  SELECT id FROM source_assets WHERE tenant_id = :'tenant_id' AND data_source_id = :'source_id'
);
DELETE FROM source_assets WHERE tenant_id = :'tenant_id' AND data_source_id = :'source_id';
DELETE FROM data_sources WHERE tenant_id = :'tenant_id' AND id = :'source_id';
COMMIT;
SQL
  fi

  docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -v ON_ERROR_STOP=1 \
    -v user_id="$user_id" >/dev/null 2>&1 <<'SQL' || true
DELETE FROM users WHERE id = :'user_id';
SQL
  find "$fixture_root" -maxdepth 1 -type f -name 'record-*.md' -delete 2>/dev/null || true
  rmdir -- "$fixture_root" 2>/dev/null || true
  rm -f -- "$output_dir"/* 2>/dev/null || true
  rmdir -- "$output_dir" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -v ON_ERROR_STOP=1 \
  -v user_id="$user_id" -v tenant_id="$tenant_id" -v email="$email" \
  -v password_hash="$password_hash" >/dev/null <<'SQL'
INSERT INTO users (
  id, tenant_id, email, normalized_email, display_name, password_hash,
  role, active, token_version, created_at, updated_at
) VALUES (
  :'user_id', :'tenant_id', :'email', :'email', 'Ingestion cancellation acceptance',
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
payload = {
    "name": f"Ingestion cancellation acceptance {fixture_key}",
    "source_type": "folder",
    "root_uri": f"/sources/knowledge/.{fixture_key}",
    "owner": "Data Operations Acceptance",
    "data_classification": "internal",
    "authorization_scopes": ["contract:ingestion-cancellation-acceptance"],
    "dataset_key": dataset_key,
    "include_globs": ["*.md"],
    "exclude_globs": [],
    "stable_seconds": 0,
    "max_file_bytes": 1048576,
    "scan_interval_seconds": 86400,
    "expected_freshness_seconds": 86400,
    "rate_limit_per_minute": 5000,
}
with open(path, "w", encoding="utf-8") as stream:
    json.dump(payload, stream, separators=(",", ":"))
PY
create_status=$(curl -sS -o "$output_dir/source.json" -w '%{http_code}' \
  -b "$cookie_jar" -H "X-CSRF-Token: $csrf_token" -H 'Content-Type: application/json' \
  --data-binary "@$output_dir/source-create.json" "$base_url/api/v1/admin/data-sources")
[[ "$create_status" == 201 ]] || { echo "source creation failed with HTTP $create_status" >&2; exit 1; }
source_id=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["id"])' "$output_dir/source.json")
[[ "$source_id" =~ ^[0-9a-f-]{36}$ ]] || { echo "source creation returned an invalid id" >&2; exit 1; }

scan_status=$(curl -sS -o "$output_dir/scan.json" -w '%{http_code}' \
  -b "$cookie_jar" -H "X-CSRF-Token: $csrf_token" -X POST \
  "$base_url/api/v1/admin/data-sources/$source_id/scan")
[[ "$scan_status" == 202 ]] || { echo "scan trigger failed with HTTP $scan_status" >&2; exit 1; }
correlation_id=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["ingestion_run_id"])' "$output_dir/scan.json")

deadline=$((SECONDS + timeout_seconds))
cancelable="false"
while (( SECONDS < deadline )); do
  curl -fsS -b "$cookie_jar" \
    "$base_url/api/v1/admin/ingestion-runs?data_source_id=$source_id&limit=10" > "$output_dir/runs.json"
  run_record=$(python3 - "$output_dir/runs.json" "$correlation_id" <<'PY'
import json
import sys

items = json.load(open(sys.argv[1], encoding="utf-8"))
run = next((item for item in items if item["workflow_id"] == sys.argv[2]), None)
if run:
    print("|".join((
        run["id"],
        run["temporal_workflow_id"] or "",
        run["temporal_run_id"] or "",
        str(run["cancelable"]).lower(),
    )))
PY
  )
  if [[ -n "$run_record" ]]; then
    IFS='|' read -r ingestion_run_id temporal_workflow_id temporal_run_id cancelable <<< "$run_record"
  fi
  if [[ "$ingestion_run_id" =~ ^[0-9a-f-]{36}$ && -n "$temporal_workflow_id" && -n "$temporal_run_id" && "$cancelable" == true ]]; then
    break
  fi
  sleep 0.1
done
[[ "$cancelable" == true ]] || {
  echo "running ingestion did not expose a cancelable bound Temporal execution" >&2
  exit 1
}

operation_key="cancel:$run_id"
python3 - "$output_dir/cancel-request.json" "$operation_key" <<'PY'
import json
import sys

with open(sys.argv[1], "w", encoding="utf-8") as stream:
    json.dump({
        "operation_key": sys.argv[2],
        "expected_state": "running",
        "reason": "Controlled real-runtime cancellation acceptance",
    }, stream, separators=(",", ":"))
PY
cancel_status=$(curl -sS -o "$output_dir/cancel.json" -w '%{http_code}' \
  -b "$cookie_jar" -H "X-CSRF-Token: $csrf_token" -H 'Content-Type: application/json' \
  --data-binary "@$output_dir/cancel-request.json" \
  "$base_url/api/v1/admin/ingestion-runs/$ingestion_run_id/cancel")
[[ "$cancel_status" == 202 ]] || {
  echo "ingestion cancellation failed with HTTP $cancel_status" >&2
  cat "$output_dir/cancel.json" >&2
  exit 1
}
duplicate_status=$(curl -sS -o "$output_dir/cancel-duplicate.json" -w '%{http_code}' \
  -b "$cookie_jar" -H "X-CSRF-Token: $csrf_token" -H 'Content-Type: application/json' \
  --data-binary "@$output_dir/cancel-request.json" \
  "$base_url/api/v1/admin/ingestion-runs/$ingestion_run_id/cancel")
[[ "$duplicate_status" == 202 ]] || { echo "idempotent cancellation failed with HTTP $duplicate_status" >&2; exit 1; }
cmp -s "$output_dir/cancel.json" "$output_dir/cancel-duplicate.json" || {
  echo "idempotent cancellation returned a different response" >&2
  exit 1
}

workflow_status=""
while (( SECONDS < deadline )); do
  workflow_status=$(docker compose exec -T temporal tctl --address temporal:7233 workflow describe \
    --workflow_id "$temporal_workflow_id" --run_id "$temporal_run_id" 2>/dev/null | python3 -c \
    'import json,sys; print(json.load(sys.stdin)["workflowExecutionInfo"]["status"])' || true)
  [[ "$workflow_status" == Canceled ]] && break
  sleep 0.5
done
[[ "$workflow_status" == Canceled ]] || {
  echo "Temporal workflow did not reach Canceled: ${workflow_status:-unknown}" >&2
  exit 1
}

curl -fsS -b "$cookie_jar" \
  "$base_url/api/v1/admin/ingestion-runs?data_source_id=$source_id&limit=10" > "$output_dir/runs-final.json"
python3 - "$output_dir/runs-final.json" "$ingestion_run_id" <<'PY'
import json
import sys

run = next(item for item in json.load(open(sys.argv[1], encoding="utf-8")) if item["id"] == sys.argv[2])
assert run["state"] == "canceled"
assert run["effective_state"] == "canceled"
assert run["cancelable"] is False
assert run["cancel_requested_at"]
assert len(run["stages"]) == 6
PY

database_evidence=$(docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -At -F '|' \
  -v ON_ERROR_STOP=1 -v tenant_id="$tenant_id" -v run_id="$ingestion_run_id" -v operation_key="$operation_key" <<'SQL'
SELECT
  (SELECT count(*) FROM ingestion_runs
    WHERE tenant_id = :'tenant_id' AND id = :'run_id' AND state = 'CANCELED'
      AND temporal_workflow_id IS NOT NULL AND temporal_run_id IS NOT NULL),
  (SELECT count(*) FROM ingestion_run_operations
    WHERE tenant_id = :'tenant_id' AND ingestion_run_id = :'run_id'
      AND operation_key = :'operation_key' AND operation_type = 'cancel' AND state = 'accepted'),
  (SELECT count(*) FROM audit_events
    WHERE tenant_id = :'tenant_id' AND resource_type = 'ingestion_run'
      AND resource_id = :'run_id' AND action = 'ingestion_run.cancel' AND outcome = 'success'),
  (SELECT count(*) FROM source_versions sv
    JOIN source_assets sa ON sa.id = sv.source_asset_id
    JOIN ingestion_runs ir ON ir.data_source_id = sa.data_source_id
    WHERE ir.id = :'run_id'
      AND (sv.parse_status = 'SUCCEEDED' OR sv.retrieval_status = 'SUCCEEDED'
        OR sv.governance_status = 'SUCCEEDED'));
SQL
)
[[ "$database_evidence" == "1|1|1|0" ]] || {
  echo "cancellation persistence or downstream-stop evidence is incomplete: $database_evidence" >&2
  exit 1
}

finished_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
cleanup
trap - EXIT INT TERM

remaining=$(docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -At -F '|' \
  -v ON_ERROR_STOP=1 -v source_id="$source_id" -v user_id="$user_id" <<'SQL'
SELECT
  (SELECT count(*) FROM data_sources WHERE id = :'source_id'),
  (SELECT count(*) FROM users WHERE id = :'user_id'),
  (SELECT count(*) FROM ingestion_runs WHERE data_source_id = :'source_id');
SQL
)
[[ "$remaining" == "0|0|0" ]] || { echo "cancellation fixture cleanup failed: $remaining" >&2; exit 1; }
[[ ! -e "$fixture_root" ]] || { echo "controlled source files remain after cleanup" >&2; exit 1; }
[[ "$temporary_objects_after" == 0 ]] || { echo "controlled object cleanup failed" >&2; exit 1; }

report=$(python3 - "$finished_at" "$timeout_seconds" "$file_count" <<'PY'
import json
import sys

print(json.dumps({
    "schema": "pharma.ingestion-cancellation-acceptance.v1",
    "status": "passed",
    "finished_at": sys.argv[1],
    "timeout_seconds": int(sys.argv[2]),
    "controlled_file_count": int(sys.argv[3]),
    "path": {
        "http_api": "passed",
        "postgresql": "passed",
        "temporal_exact_execution": "passed",
        "worker_cooperative_stop": "passed",
        "immutable_object_store": "passed",
    },
    "idempotency": "passed",
    "audit": "passed",
    "downstream_processing_after_cancel": 0,
    "temporary_database_records_after": 0,
    "temporary_source_files_after": 0,
    "temporary_objects_after": 0,
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
