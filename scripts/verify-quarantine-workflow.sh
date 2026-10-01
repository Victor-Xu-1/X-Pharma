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
      echo "Usage: verify-quarantine-workflow.sh [--timeout-seconds N] [--output FILE]"
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
for service in api worker postgres temporal clamav parser; do
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
fixture_key="quarantine-acceptance-$run_id"
fixture_root="$knowledge_source_root/.$fixture_key"
fixture_file="$fixture_root/eicar-$run_id.md"
output_dir="/tmp/pharma-quarantine-acceptance-$$"
cookie_jar="$output_dir/cookies.txt"
mkdir -m 0700 "$output_dir"
mkdir -m 0755 "$fixture_root"
[[ "$(realpath "$fixture_root")" == "$knowledge_source_root/.$fixture_key" ]] || {
  echo "controlled fixture escaped the mounted source root" >&2
  exit 1
}
python3 - "$fixture_file" <<'PY'
from pathlib import Path
import sys

Path(sys.argv[1]).write_text(
    "X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*\n",
    encoding="ascii",
)
PY
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
  echo "an active licensed dataset is required for quarantine acceptance" >&2
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
object_cleanup_failures=0
cleanup_done=false

cleanup() {
  [[ "$cleanup_done" == false ]] || return 0
  cleanup_done=true

  if [[ -n "$raw_object_uri" && "$raw_sha256" =~ ^[0-9a-f]{64}$ ]]; then
    if ! docker compose exec -T worker python - "$raw_object_uri" "$raw_sha256" >/dev/null <<'PY'
import sys
from pharma_intel.config import get_settings
from pharma_intel.object_store import build_object_store

build_object_store(get_settings()).delete(sys.argv[1], sys.argv[2])
PY
    then
      object_cleanup_failures=$((object_cleanup_failures + 1))
    fi
  fi

  if [[ -n "$source_id" ]]; then
    docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -v ON_ERROR_STOP=1 \
      -v tenant_id="$tenant_id" -v source_id="$source_id" >/dev/null <<'SQL' || true
BEGIN;
CREATE TEMP TABLE fixture_versions AS
SELECT sv.id, sv.source_document_id, sv.retrieval_projection_id
FROM source_versions sv
JOIN source_assets sa ON sa.id = sv.source_asset_id
WHERE sv.tenant_id = :'tenant_id' AND sa.data_source_id = :'source_id';
CREATE TEMP TABLE fixture_events AS
SELECT oe.id FROM outbox_events oe
WHERE oe.tenant_id = :'tenant_id'
  AND oe.aggregate_type IN ('source_version', 'source_asset')
  AND oe.aggregate_id IN (
    SELECT id FROM fixture_versions
    UNION ALL
    SELECT id FROM source_assets WHERE data_source_id = :'source_id'
  );
DELETE FROM projection_deliveries WHERE outbox_event_id IN (SELECT id FROM fixture_events);
DELETE FROM outbox_events WHERE id IN (SELECT id FROM fixture_events);
DELETE FROM source_version_operations WHERE source_version_id IN (SELECT id FROM fixture_versions);
ALTER TABLE source_version_quarantine_decisions DISABLE TRIGGER immutable_source_version_quarantine_decisions;
DELETE FROM source_version_quarantine_decisions WHERE source_version_id IN (SELECT id FROM fixture_versions);
ALTER TABLE source_version_quarantine_decisions ENABLE TRIGGER immutable_source_version_quarantine_decisions;
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
DELETE FROM account_invitations WHERE created_by_user_id IN (SELECT id FROM users WHERE id = :'user_id')
  OR claimed_user_id IN (SELECT id FROM users WHERE id = :'user_id');
DELETE FROM user_sessions WHERE user_id = :'user_id';
DELETE FROM organization_memberships WHERE user_id = :'user_id';
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
  id, home_tenant_id, email, normalized_email, display_name, password_hash,
  active, token_version, created_at, updated_at
) VALUES (
  :'user_id', :'tenant_id', :'email', :'email', 'Quarantine acceptance',
  :'password_hash', true, 1, now(), now()
);
INSERT INTO organization_memberships (tenant_id, user_id, role, active, token_version, created_at, updated_at)
VALUES (:'tenant_id', :'user_id', 'ADMIN', true, 1, now(), now());
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
    "name": f"Quarantine acceptance {fixture_key}",
    "source_type": "folder",
    "root_uri": f"/sources/knowledge/.{fixture_key}",
    "owner": "Security Operations Acceptance",
    "data_classification": "restricted",
    "authorization_scopes": ["contract:quarantine-acceptance"],
    "dataset_key": dataset_key,
    "include_globs": ["*.md", "**/*.md"],
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

set +e
docker compose exec -T worker pharma-ingest once --source-id "$source_id" >"$output_dir/initial-ingestion.log" 2>&1
ingest_status=$?
set -e
[[ "$ingest_status" -ne 0 ]] || { echo "EICAR ingestion unexpectedly succeeded" >&2; exit 1; }

asset_id=$(curl -fsS -b "$cookie_jar" \
  "$base_url/api/v1/admin/source-assets?data_source_id=$source_id&limit=10&offset=0" | \
  python3 -c 'import json,sys; p=json.load(sys.stdin); assert p["total"]==1; print(p["items"][0]["id"])')
[[ "$asset_id" =~ ^[0-9a-f-]{36}$ ]] || { echo "invalid source asset identifier" >&2; exit 1; }
curl -fsS -b "$cookie_jar" "$base_url/api/v1/admin/source-assets/$asset_id" > "$output_dir/asset.json"
version_id=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["versions"][0]["id"])' "$output_dir/asset.json")
[[ "$version_id" =~ ^[0-9a-f-]{36}$ ]] || { echo "invalid source version identifier" >&2; exit 1; }

curl -fsS -b "$cookie_jar" "$base_url/api/v1/admin/quarantine-cases/$version_id" > "$output_dir/case-initial.json"
python3 - "$output_dir/asset.json" "$output_dir/case-initial.json" <<'PY'
import json
import sys

version = json.load(open(sys.argv[1], encoding="utf-8"))["versions"][0]
case = json.load(open(sys.argv[2], encoding="utf-8"))
assert version["state"] == "failed"
assert version["malware_scan_status"] == "failed"
assert version["parse_status"] == version["retrieval_status"] == version["governance_status"] == "not_started"
assert version["error_code"] == "malware_detected"
assert version["extracted_text_sha256"] is None
assert version["quarantine_status"] == "pending_review"
assert version["quarantine_version"] == 1
assert case["quarantine_status"] == "pending_review"
assert case["quarantine_version"] == 1
assert "EICAR" in (case["threat_name"] or "").upper()
assert [item["action"] for item in case["decisions"]] == ["scan_detected"]
PY

IFS='|' read -r raw_object_uri raw_sha256 blocked_records < <(
  docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -At -F '|' -v ON_ERROR_STOP=1 \
    -v version_id="$version_id" <<'SQL'
SELECT sv.raw_object_uri, sv.content_sha256,
       (SELECT count(*) FROM source_documents sd WHERE sd.id=sv.source_document_id)
       + (SELECT count(*) FROM extraction_runs er WHERE er.source_version_id=sv.id)
       + (SELECT count(*) FROM retrieval_projections rp WHERE rp.id=sv.retrieval_projection_id)
FROM source_versions sv WHERE sv.id=:'version_id';
SQL
)
[[ "$raw_object_uri" == file://* && "$raw_sha256" =~ ^[0-9a-f]{64}$ && "$blocked_records" == 0 ]] || {
  echo "malicious version crossed a blocked processing boundary" >&2
  exit 1
}

submit_decision() {
  local action=$1 expected_version=$2 operation_key=$3 reason=$4 response_path=$5 expected_http=$6
  python3 - "$output_dir/decision-request.json" "$action" "$expected_version" "$operation_key" "$reason" <<'PY'
import json, sys
path, action, version, key, reason = sys.argv[1:]
json.dump({"action": action, "expected_version": int(version), "operation_key": key, "reason": reason},
          open(path, "w", encoding="utf-8"), separators=(",", ":"))
PY
  local code
  code=$(curl -sS -o "$response_path" -w '%{http_code}' -b "$cookie_jar" \
    -H "X-CSRF-Token: $csrf_token" -H 'Content-Type: application/json' \
    --data-binary "@$output_dir/decision-request.json" \
    "$base_url/api/v1/admin/quarantine-cases/$version_id/decisions")
  [[ "$code" == "$expected_http" ]] || {
    echo "$action decision returned HTTP $code instead of $expected_http" >&2
    cat "$response_path" >&2
    return 1
  }
}

hold_key="quarantine:hold:$run_id"
submit_decision hold 1 "$hold_key" "Retain the EICAR fixture for controlled security review" "$output_dir/hold.json" 200
submit_decision hold 1 "$hold_key" "Retain the EICAR fixture for controlled security review" "$output_dir/hold-duplicate.json" 200
cmp -s "$output_dir/hold.json" "$output_dir/hold-duplicate.json" || {
  echo "quarantine decision idempotency response drifted" >&2
  exit 1
}

rescan_key="quarantine:rescan:$run_id"
submit_decision rescan 2 "$rescan_key" "Updated signatures require a complete controlled malware rescan" \
  "$output_dir/rescan.json" 202
workflow_id=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["workflow_id"])' "$output_dir/rescan.json")
[[ "$workflow_id" == "source-version-reprocess-$version_id" ]] || { echo "unexpected rescan workflow id" >&2; exit 1; }

deadline=$((SECONDS + timeout_seconds))
while (( SECONDS < deadline )); do
  curl -fsS -b "$cookie_jar" "$base_url/api/v1/admin/quarantine-cases/$version_id" > "$output_dir/case-rescanned.json"
  state=$(python3 -c 'import json,sys; p=json.load(open(sys.argv[1])); print("{}|{}".format(p["quarantine_status"],p["quarantine_version"]))' "$output_dir/case-rescanned.json")
  [[ "$state" == "pending_review|4" ]] && break
  sleep 2
done
[[ "$state" == "pending_review|4" ]] || { echo "malicious rescan did not return to review: $state" >&2; exit 1; }
python3 - "$output_dir/case-rescanned.json" <<'PY'
import json, sys
case = json.load(open(sys.argv[1], encoding="utf-8"))
assert [item["action"] for item in case["decisions"]] == ["scan_detected", "hold", "rescan", "scan_detected"]
assert "EICAR" in (case["threat_name"] or "").upper()
PY

workflow_status=""
while (( SECONDS < deadline )); do
  workflow_status=$(docker compose exec -T temporal tctl --address temporal:7233 workflow describe \
    --workflow_id "$workflow_id" 2>/dev/null | python3 -c \
    'import json,sys; print(json.load(sys.stdin)["workflowExecutionInfo"]["status"])' 2>/dev/null || true)
  [[ "$workflow_status" == Completed ]] && break
  sleep 2
done
[[ "$workflow_status" == Completed ]] || { echo "quarantine rescan workflow is not completed" >&2; exit 1; }

submit_decision reject 4 "quarantine:reject:$run_id" \
  "Confirmed EICAR content must remain permanently rejected" "$output_dir/reject.json" 200

python3 - "$output_dir/replay-request.json" "$run_id" <<'PY'
import json, sys
json.dump({
    "operation_key": f"quarantine:generic-replay:{sys.argv[2]}",
    "expected_state": "failed",
    "expected_error_code": "malware_detected",
    "from_stage": "malware_scan",
    "reason": "Generic replay must remain blocked after permanent rejection",
}, open(sys.argv[1], "w", encoding="utf-8"), separators=(",", ":"))
PY
replay_status=$(curl -sS -o "$output_dir/replay-blocked.json" -w '%{http_code}' -b "$cookie_jar" \
  -H "X-CSRF-Token: $csrf_token" -H 'Content-Type: application/json' \
  --data-binary "@$output_dir/replay-request.json" \
  "$base_url/api/v1/admin/source-versions/$version_id/replay")
[[ "$replay_status" == 409 ]] || { echo "generic replay was not blocked" >&2; exit 1; }
python3 - "$output_dir/replay-blocked.json" <<'PY'
import json, sys
detail = json.load(open(sys.argv[1], encoding="utf-8"))["detail"]
assert detail["code"] == "quarantine_decision_required"
assert detail["quarantine_status"] == "rejected"
PY

submit_decision rescan 5 "quarantine:rejected-rescan:$run_id" \
  "Rejected content cannot be released by a standard rescan" "$output_dir/rejected-rescan.json" 409

integrity=$(docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -At -F '|' -v ON_ERROR_STOP=1 \
  -v tenant_id="$tenant_id" -v version_id="$version_id" <<'SQL'
SELECT
  (SELECT count(*) FROM source_version_quarantine_decisions
   WHERE tenant_id=:'tenant_id' AND source_version_id=:'version_id'),
  (SELECT count(*) FROM source_version_operations
   WHERE tenant_id=:'tenant_id' AND source_version_id=:'version_id' AND state='accepted'),
  (SELECT count(*) FROM audit_events
   WHERE tenant_id=:'tenant_id' AND resource_type='source_version' AND resource_id=:'version_id'
     AND action LIKE 'source_version.quarantine.%' AND outcome='success'),
  (SELECT count(*) FROM pg_class c
   WHERE c.relname IN ('ingestion_run_operations','source_version_operations','source_version_quarantine_decisions')
     AND c.relrowsecurity AND c.relforcerowsecurity),
  (SELECT count(*) FROM pg_policies
   WHERE tablename IN ('ingestion_run_operations','source_version_operations','source_version_quarantine_decisions')
     AND policyname='tenant_isolation');
SQL
)
[[ "$integrity" == "5|3|3|3|3" ]] || { echo "quarantine integrity evidence is incomplete: $integrity" >&2; exit 1; }

if docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -v ON_ERROR_STOP=1 \
  -v version_id="$version_id" >/dev/null 2>&1 <<'SQL'
UPDATE source_version_quarantine_decisions SET reason='mutation must fail'
WHERE source_version_id=:'version_id';
SQL
then
  echo "append-only quarantine decision mutation unexpectedly succeeded" >&2
  exit 1
fi

final_state=$(docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -At -F '|' -v ON_ERROR_STOP=1 \
  -v version_id="$version_id" <<'SQL'
SELECT quarantine_status, quarantine_version, malware_scan_status, parse_status,
       retrieval_status, governance_status, error_code,
       CASE WHEN extracted_text_object_uri IS NULL AND extracted_text_sha256 IS NULL THEN 0 ELSE 1 END
FROM source_versions WHERE id=:'version_id';
SQL
)
[[ "$final_state" == "REJECTED|5|FAILED|NOT_STARTED|NOT_STARTED|NOT_STARTED|malware_detected|0" ]] || {
  echo "final quarantine state is invalid: $final_state" >&2
  exit 1
}

finished_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
cleanup
trap - EXIT INT TERM

remaining=$(docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -At -F '|' -v ON_ERROR_STOP=1 \
  -v source_id="$source_id" -v user_id="$user_id" -v version_id="$version_id" <<'SQL'
SELECT (SELECT count(*) FROM data_sources WHERE id=:'source_id'),
       (SELECT count(*) FROM users WHERE id=:'user_id'),
       (SELECT count(*) FROM source_versions WHERE id=:'version_id'),
       (SELECT count(*) FROM source_version_quarantine_decisions WHERE source_version_id=:'version_id');
SQL
)
[[ "$remaining" == "0|0|0|0" && "$object_cleanup_failures" == 0 && ! -e "$fixture_file" ]] || {
  echo "quarantine acceptance cleanup failed: db=$remaining objects=$object_cleanup_failures" >&2
  exit 1
}

report=$(python3 - "$finished_at" "$timeout_seconds" <<'PY'
import json, sys
print(json.dumps({
  "schema":"pharma.quarantine-workflow-acceptance.v1",
  "status":"passed",
  "finished_at":sys.argv[1],
  "timeout_seconds":int(sys.argv[2]),
  "path":{"real_eicar":"passed","clamav":"passed","http_api":"passed","postgresql":"passed",
          "temporal":"passed","worker":"passed","parser_bypass_prevention":"passed"},
  "governance":{"operator_hold":"passed","controlled_rescan":"passed","permanent_reject":"passed",
                "generic_replay_blocked":"passed","idempotency":"passed","audit":"passed",
                "append_only_history":"passed","tenant_rls":"passed"},
  "credentials_recorded":False,
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
