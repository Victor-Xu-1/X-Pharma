#!/usr/bin/env bash
set -Eeuo pipefail

umask 077

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
source "$root/scripts/lib/entry_staging.sh"
web_url="http://127.0.0.1:18380"
mcp_url="http://127.0.0.1:18390/mcp"
output_path=""

usage() {
  cat <<'EOF'
Usage: verify-entry-consistency.sh [options]

Create one isolated entity through the authenticated human API and verify that
the Web and billed MCP read/search paths return the same canonical facts.

Options:
  --web-url URL    Human Web/API origin (default: http://127.0.0.1:18380).
  --mcp-url URL    MCP endpoint (default: http://127.0.0.1:18390/mcp).
  --output FILE    Write an atomic machine-readable acceptance report.
  -h, --help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --web-url)
      [[ $# -ge 2 ]] || { echo "--web-url requires a value" >&2; exit 2; }
      web_url=$2
      shift 2
      ;;
    --mcp-url)
      [[ $# -ge 2 ]] || { echo "--mcp-url requires a value" >&2; exit 2; }
      mcp_url=$2
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

[[ -n "${TEST_MCP_ACCESS_TOKEN:-}" ]] || {
  echo "TEST_MCP_ACCESS_TOKEN is required" >&2
  exit 1
}
for command in awk curl docker find openssl python3 realpath uv; do
  command -v "$command" >/dev/null 2>&1 || {
    echo "required command is unavailable: $command" >&2
    exit 1
  }
done
for url in "$web_url" "$mcp_url"; do
  case "$url" in
    http://*|https://*) ;;
    *) echo "entry URLs must use HTTP or HTTPS" >&2; exit 2 ;;
  esac
done

protocol_baseline=""
while IFS= read -r raw_line || [[ -n "$raw_line" ]]; do
  line=${raw_line%%#*}
  if [[ "$line" =~ ^MCP_PROTOCOL_BASELINE=([0-9]{4}-[0-9]{2}-[0-9]{2})$ ]]; then
    protocol_baseline=${BASH_REMATCH[1]}
  fi
done < "$root/deploy/protocol/versions.env"
[[ -n "$protocol_baseline" ]] || {
  echo "MCP_PROTOCOL_BASELINE is missing or invalid" >&2
  exit 1
}

export COMPOSE_FILE="${COMPOSE_FILE:-compose.yaml:compose.dev.yaml:compose.telemetry.yaml}"
cd "$root"
compose=(docker compose)
source "$root/scripts/lib/mcp_fixture_http.sh"
pg_user=$(docker compose exec -T postgres printenv POSTGRES_USER | tr -d '\r')
pg_db=$(docker compose exec -T postgres printenv POSTGRES_DB | tr -d '\r')
token_prefix=${TEST_MCP_ACCESS_TOKEN:0:12}
[[ "$token_prefix" =~ ^[A-Za-z0-9_-]{8,16}$ ]] || {
  echo "MCP token does not expose a safe API key prefix" >&2
  exit 1
}
tenant_record=$(
  docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -At -F '|' -v ON_ERROR_STOP=1 \
    -c "SELECT t.id, t.slug FROM api_keys k JOIN tenants t ON t.id = k.tenant_id WHERE k.prefix = '$token_prefix' AND k.active IS TRUE AND k.revoked_at IS NULL AND t.active IS TRUE"
)
tenant_count=$(printf '%s\n' "$tenant_record" | awk 'NF { count += 1 } END { print count + 0 }')
IFS='|' read -r tenant_id tenant_slug <<< "$tenant_record"
if [[ "$tenant_count" != "1" || ! "$tenant_id" =~ ^[0-9a-f-]{36}$ || -z "$tenant_slug" ]]; then
  echo "MCP token did not resolve to exactly one active tenant" >&2
  exit 1
fi
opensearch_index_prefix=$(
  docker compose exec -T worker sh -ec 'printf %s "${OPENSEARCH_INDEX_PREFIX:-pharma}"'
)
[[ "$opensearch_index_prefix" =~ ^[a-z0-9][a-z0-9-]{0,79}$ ]] || {
  echo "Runtime returned an unsafe OpenSearch index prefix" >&2
  exit 1
}

stale_accounts=$(docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -At -v ON_ERROR_STOP=1 \
  -c "SELECT count(*) FROM users WHERE normalized_email LIKE 'entry-consistency-%@example.test'")
stale_entities=$(docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -At -v ON_ERROR_STOP=1 \
  -c "SELECT count(*) FROM entities WHERE tenant_id = '$tenant_id' AND attributes ->> 'acceptance_fixture_kind' = 'entry_consistency'")
[[ "$stale_accounts" == "0" && "$stale_entities" == "0" ]] || {
  echo "Refusing to run with stale entry consistency fixtures" >&2
  exit 1
}

fixture_marker="entry-$(python3 -c 'import uuid; print(uuid.uuid4().hex[:16])')"
email="$fixture_marker@example.test"
password="$(openssl rand -hex 24)Aa1!"
fixture_parent=$(realpath -e -- "${TMPDIR:-/tmp}")
fixture_root=$(mktemp -d "$fixture_parent/pharma-entry-consistency.XXXXXX")
fixture_ids_path="$fixture_root/entity-ids"
touch "$fixture_ids_path"
fixture_active=1

remove_fixtures() {
  local require_entity=${1:-0}
  local cleanup_errors=0
  local deleted_entities=""
  [[ $fixture_active -eq 1 ]] || return 0
  docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -At -v ON_ERROR_STOP=1 \
    -c "SELECT id FROM entities WHERE tenant_id = '$tenant_id' AND attributes ->> 'acceptance_fixture_marker' = '$fixture_marker' ORDER BY id" \
    > "$fixture_ids_path" || cleanup_errors=1
  deleted_entities=$(docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -At -v ON_ERROR_STOP=1 <<SQL
BEGIN;
CREATE TEMP TABLE consistency_entities (id varchar(36) PRIMARY KEY) ON COMMIT DROP;
INSERT INTO consistency_entities
SELECT id FROM entities
WHERE tenant_id = '$tenant_id' AND attributes ->> 'acceptance_fixture_marker' = '$fixture_marker';
DELETE FROM projection_deliveries
WHERE outbox_event_id IN (
  SELECT id FROM outbox_events
  WHERE tenant_id = '$tenant_id' AND aggregate_type = 'entity'
    AND aggregate_id IN (SELECT id FROM consistency_entities)
);
DELETE FROM outbox_events
WHERE tenant_id = '$tenant_id' AND aggregate_type = 'entity'
  AND aggregate_id IN (SELECT id FROM consistency_entities);
DELETE FROM entity_resolution_decisions
WHERE tenant_id = '$tenant_id' AND resolution_case_id IN (
  SELECT id FROM entity_resolution_cases
  WHERE tenant_id = '$tenant_id'
    AND (
      source_entity_id IN (SELECT id FROM consistency_entities)
      OR candidate_entity_id IN (SELECT id FROM consistency_entities)
    )
);
DELETE FROM entity_canonical_links
WHERE tenant_id = '$tenant_id'
  AND (
    alias_entity_id IN (SELECT id FROM consistency_entities)
    OR canonical_entity_id IN (SELECT id FROM consistency_entities)
  );
DELETE FROM entity_resolution_cases
WHERE tenant_id = '$tenant_id'
  AND (
    source_entity_id IN (SELECT id FROM consistency_entities)
    OR candidate_entity_id IN (SELECT id FROM consistency_entities)
  );
DELETE FROM entity_ontology_mappings
WHERE tenant_id = '$tenant_id' AND entity_id IN (SELECT id FROM consistency_entities);
DELETE FROM entity_identifiers
WHERE tenant_id = '$tenant_id' AND entity_id IN (SELECT id FROM consistency_entities);
DELETE FROM entity_aliases
WHERE tenant_id = '$tenant_id' AND entity_id IN (SELECT id FROM consistency_entities);
WITH deleted AS (
  DELETE FROM entities
  WHERE tenant_id = '$tenant_id' AND id IN (SELECT id FROM consistency_entities)
  RETURNING 1
)
SELECT count(*) FROM deleted;
DELETE FROM user_sessions WHERE user_id IN (SELECT id FROM users WHERE normalized_email = '$email');
DELETE FROM organization_memberships WHERE user_id IN (SELECT id FROM users WHERE normalized_email = '$email');
DELETE FROM users WHERE normalized_email = '$email';
COMMIT;
SQL
  ) || cleanup_errors=1
  if [[ $require_entity -eq 1 ]]; then
    [[ "$deleted_entities" == *$'1\nDELETE 1\nCOMMIT' ]] || cleanup_errors=1
  fi
  while IFS= read -r entity_id; do
    [[ -n "$entity_id" ]] || continue
    [[ "$entity_id" =~ ^[0-9a-f-]{36}$ ]] || { cleanup_errors=1; continue; }
    mcp_fixture_opensearch none --request DELETE \
      "http://localhost:9200/$opensearch_index_prefix-entities-write/_doc/$tenant_id:$entity_id?routing=$tenant_id&refresh=true" \
      > "$fixture_root/opensearch-delete-$entity_id.json" || cleanup_errors=1
  done < "$fixture_ids_path"
  remaining_accounts=$(docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -At -v ON_ERROR_STOP=1 \
    -c "SELECT count(*) FROM users WHERE normalized_email = '$email'") || cleanup_errors=1
  remaining_entities=$(docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -At -v ON_ERROR_STOP=1 \
    -c "SELECT count(*) FROM entities WHERE tenant_id = '$tenant_id' AND attributes ->> 'acceptance_fixture_marker' = '$fixture_marker'") || cleanup_errors=1
  [[ "$remaining_accounts" == "0" && "$remaining_entities" == "0" ]] || cleanup_errors=1
  entry_staging_remove "$fixture_parent" "$fixture_root" || cleanup_errors=1
  fixture_active=0
  [[ $cleanup_errors -eq 0 ]]
}

cleanup_on_exit() {
  status=$?
  trap - EXIT INT TERM
  set +e
  remove_fixtures 0
  exit "$status"
}
trap cleanup_on_exit EXIT INT TERM

docker compose run --rm --no-deps migrate pharma-bootstrap \
  --tenant-slug "$tenant_slug" \
  --tenant-name "Entry Consistency" \
  --skip-api-key \
  --admin-email "$email" \
  --admin-password "$password" \
  --admin-name "Entry Consistency" >/dev/null

result=$(
  ENTRY_TEST_EMAIL="$email" ENTRY_TEST_PASSWORD="$password" \
    uv run python -m scripts.entry_consistency_probe \
      --web-url "$web_url" \
      --mcp-url "$mcp_url" \
      --fixture-marker "$fixture_marker" \
      --expected-protocol-version "$protocol_baseline"
)
remove_fixtures 1
trap - EXIT INT TERM
printf '%s\n' "$result"

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
  [[ ! -e "$output_path" ]] || {
    echo "refusing to overwrite entry consistency evidence: $output_path" >&2
    exit 1
  }
  temporary="$output_path.partial.$$"
  output_complete=0
  cleanup_output() {
    status=$?
    trap - EXIT INT TERM
    if [[ $output_complete -ne 1 ]]; then
      case "$temporary" in
        "$output_path.partial."*) rm -f -- "$temporary" ;;
        *) echo "refusing to clean unexpected entry consistency evidence path: $temporary" >&2 ;;
      esac
    fi
    exit "$status"
  }
  trap cleanup_output EXIT INT TERM
  printf '%s\n' "$result" > "$temporary"
  python3 - "$temporary" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
document = json.loads(path.read_text(encoding="utf-8"))
if document.get("status") != "passed":
    raise SystemExit("entry consistency report did not pass")
document["temporary_accounts_after"] = 0
document["temporary_entities_after"] = 0
document["credentials_recorded"] = False
path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
  chmod 600 "$temporary"
  mv -- "$temporary" "$output_path"
  output_complete=1
  trap - EXIT INT TERM
  printf 'entry_consistency_report=%s\n' "$output_path"
fi

printf 'entry_consistency_status=passed\n'
