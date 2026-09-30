#!/usr/bin/env bash
set -euo pipefail

umask 077

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
versions_path="$root/deploy/protocol/versions.env"
mcp_url="http://127.0.0.1:18390/mcp"
node_path="node"
pnpm_path="pnpm"
uv_path="uv"
cache_root="${XDG_CACHE_HOME:-$HOME/.cache}/pharma-intelligence/mcp-inspector"
output_path=""
async_task_only=0
seed_local_commercial_fixture=0
project_name="${COMPOSE_PROJECT_NAME:-pharma-intelligence}"

usage() {
  cat <<'EOF'
Usage: verify-mcp-interoperability.sh [options]

Run the pinned official MCP Inspector CLI and Python MCP SDK against the same
streamable HTTP endpoint, isolated fixture, identity and billing boundary.

Options:
  --mcp-url URL       MCP endpoint (default: http://127.0.0.1:18390/mcp).
  --node-path PATH    Node.js executable (default: node).
  --pnpm-path PATH    pnpm executable (default: pnpm).
  --uv-path PATH      uv executable (default: uv).
  --cache-root DIR    Versioned Inspector cache directory.
  --output FILE       Write an atomic machine-readable acceptance report.
  --async-task-only   Run the isolated privileged async-task interoperability gate.
  --seed-local-commercial-fixture
                      Provision a disposable paid contract for the local fixture.
  --project-name NAME Compose project owning the runtime (default: COMPOSE_PROJECT_NAME or pharma-intelligence).
  -h, --help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mcp-url)
      [[ $# -ge 2 ]] || { echo "--mcp-url requires a value" >&2; exit 2; }
      mcp_url=$2
      shift 2
      ;;
    --node-path)
      [[ $# -ge 2 ]] || { echo "--node-path requires a value" >&2; exit 2; }
      node_path=$2
      shift 2
      ;;
    --pnpm-path)
      [[ $# -ge 2 ]] || { echo "--pnpm-path requires a value" >&2; exit 2; }
      pnpm_path=$2
      shift 2
      ;;
    --uv-path)
      [[ $# -ge 2 ]] || { echo "--uv-path requires a value" >&2; exit 2; }
      uv_path=$2
      shift 2
      ;;
    --cache-root)
      [[ $# -ge 2 ]] || { echo "--cache-root requires a value" >&2; exit 2; }
      cache_root=$2
      shift 2
      ;;
    --output)
      [[ $# -ge 2 ]] || { echo "--output requires a value" >&2; exit 2; }
      output_path=$2
      shift 2
      ;;
    --async-task-only)
      async_task_only=1
      shift
      ;;
    --seed-local-commercial-fixture)
      seed_local_commercial_fixture=1
      shift
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

if [[ $async_task_only -ne 1 ]]; then
  [[ -n "${TEST_MCP_ACCESS_TOKEN:-}" ]] || {
    echo "TEST_MCP_ACCESS_TOKEN is required" >&2
    exit 1
  }
fi
for command in "$node_path" "$pnpm_path" "$uv_path" python3 realpath flock; do
  command -v "$command" >/dev/null 2>&1 || {
    echo "required command is unavailable: $command" >&2
    exit 1
  }
done
case "$mcp_url" in
  http://*|https://*) ;;
  *)
    echo "MCP URL must use HTTP or HTTPS" >&2
    exit 2
    ;;
esac
[[ "$project_name" =~ ^[a-z0-9][a-z0-9_-]*$ ]] || {
  echo "--project-name must contain only lowercase letters, digits, underscores or hyphens" >&2
  exit 2
}

version=""
sdk_version=""
protocol_baseline=""
while IFS= read -r raw_line || [[ -n "$raw_line" ]]; do
  line=${raw_line%%#*}
  [[ -n "$line" ]] || continue
  if [[ "$line" =~ ^MCP_INSPECTOR_VERSION=([0-9]+\.[0-9]+\.[0-9]+)$ ]]; then
    version=${BASH_REMATCH[1]}
  elif [[ "$line" =~ ^MCP_PYTHON_SDK_VERSION=([0-9]+\.[0-9]+\.[0-9]+)$ ]]; then
    sdk_version=${BASH_REMATCH[1]}
  elif [[ "$line" =~ ^MCP_PROTOCOL_BASELINE=([0-9]{4}-[0-9]{2}-[0-9]{2})$ ]]; then
    protocol_baseline=${BASH_REMATCH[1]}
  fi
done < "$versions_path"
[[ -n "$version" ]] || {
  echo "MCP_INSPECTOR_VERSION is missing or invalid in $versions_path" >&2
  exit 1
}
[[ -n "$sdk_version" ]] || {
  echo "MCP_PYTHON_SDK_VERSION is missing or invalid in $versions_path" >&2
  exit 1
}
[[ -n "$protocol_baseline" ]] || {
  echo "MCP_PROTOCOL_BASELINE is missing or invalid in $versions_path" >&2
  exit 1
}

mkdir -p "$cache_root"
cache_root=$(realpath "$cache_root")
[[ "$cache_root" != "/" ]] || {
  echo "cache root cannot be the filesystem root" >&2
  exit 2
}
chmod 700 "$cache_root"
exec 9>"$cache_root/.install.lock"
flock 9

version_dir="$cache_root/$version"
package="$version_dir/node_modules/@modelcontextprotocol/inspector/cli/build/cli.js"
package_manifest="$version_dir/node_modules/@modelcontextprotocol/inspector/package.json"
if [[ ! -f "$package" || ! -f "$package_manifest" ]]; then
  staging=$(mktemp -d "$cache_root/.install-$version.XXXXXX")
  complete=0
  cleanup_staging() {
    trap - EXIT INT TERM
    if [[ $complete -ne 1 ]]; then
      case "$staging" in
        "$cache_root"/.install-*) rm -rf -- "$staging" ;;
        *) echo "refusing to remove unexpected Inspector staging path: $staging" >&2 ;;
      esac
    fi
  }
  trap cleanup_staging EXIT INT TERM
  (
    cd "$staging"
    "$pnpm_path" init >/dev/null
    "$pnpm_path" add --save-exact --config.node-linker=hoisted \
      "@modelcontextprotocol/inspector@$version" >/dev/null
  )
  installed=$("$node_path" -e 'console.log(require(process.argv[1]).version)' \
    "$staging/node_modules/@modelcontextprotocol/inspector/package.json")
  [[ "$installed" == "$version" ]] || {
    echo "pinned MCP Inspector installation returned version $installed" >&2
    exit 1
  }
  [[ -f "$staging/node_modules/@modelcontextprotocol/inspector/cli/build/cli.js" ]] || {
    echo "pinned MCP Inspector CLI was not installed" >&2
    exit 1
  }
  case "$version_dir" in
    "$cache_root/$version") rm -rf -- "$version_dir" ;;
    *) echo "refusing to replace unexpected Inspector cache path: $version_dir" >&2; exit 1 ;;
  esac
  mv "$staging" "$version_dir"
  complete=1
  trap - EXIT INT TERM
fi

installed=$("$node_path" -e 'console.log(require(process.argv[1]).version)' "$package_manifest")
[[ "$installed" == "$version" ]] || {
  echo "cached MCP Inspector version mismatch: expected=$version actual=$installed" >&2
  exit 1
}

declared_bin=$("$node_path" -e \
  'const p=require(process.argv[1]); console.log(p.bin?.["mcp-inspector"] || "")' \
  "$package_manifest")
[[ "$declared_bin" == "cli/build/cli.js" ]] || {
  echo "unexpected MCP Inspector public CLI entry: $declared_bin" >&2
  exit 1
}
package="$version_dir/node_modules/@modelcontextprotocol/inspector/$declared_bin"
[[ -f "$package" ]] || { echo "declared MCP Inspector CLI is missing" >&2; exit 1; }

if [[ $async_task_only -eq 1 ]]; then
  [[ -n "$output_path" ]] || {
    echo "--output is required with --async-task-only" >&2
    exit 2
  }
  (
    cd "$root"
    "$uv_path" run python -m scripts.mcp_async_task_probe \
      --node "$(command -v "$node_path")" \
      --inspector-cli "$package" \
      --inspector-version "$version" \
      --output "$output_path"
  )
  exit 0
fi

acceptance_query=${MCP_ACCEPTANCE_QUERY:-}
fixture_enabled=0
commercial_fixture_enabled=0
fixture_root=""
fixture_target_id_a=""
fixture_target_id_b=""
fixture_drug_id_a=""
fixture_drug_id_b=""
fixture_program_id_a=""
fixture_program_id_b=""
fixture_tenant_id=""
opensearch_index_prefix=""
commercial_client_key=""
commercial_account_key=""
commercial_subscription_key=""
commercial_rate_card_key=""
commercial_credit_reference=""
commercial_actor_id=""
if [[ -z "${COMPOSE_FILE:-}" ]]; then
  if [[ -n "${MSYSTEM:-}" ]]; then
    export COMPOSE_FILE="compose.yaml;compose.dev.yaml;compose.telemetry.yaml"
  else
    export COMPOSE_FILE="compose.yaml:compose.dev.yaml:compose.telemetry.yaml"
  fi
fi
compose=(docker compose --project-name "$project_name")

remove_local_fixture() {
  local require_present=${1:-1}
  local cleanup_errors=0
  local database_deleted=""
  local programs_deleted=""
  local database_remaining=""
  local opensearch_status=""
  if [[ $commercial_fixture_enabled -eq 1 ]]; then
    if ! cleanup_local_commercial_fixture; then
      cleanup_errors=1
    else
      commercial_fixture_enabled=0
    fi
  fi
  [[ $fixture_enabled -eq 1 ]] || return 0
  for fixture_target_id in "$fixture_target_id_a" "$fixture_target_id_b"; do
    curl --disable --silent --show-error --request DELETE \
      "http://127.0.0.1:9200/$opensearch_index_prefix-entities-write/_doc/$fixture_tenant_id:$fixture_target_id?routing=$fixture_tenant_id&refresh=true" \
      --output "$fixture_root/opensearch-delete-$fixture_target_id.json" || cleanup_errors=1
  done
  if ! python3 - "$fixture_root" "$require_present" "$fixture_target_id_a" "$fixture_target_id_b" <<'PY'
import json
import sys
from pathlib import Path

allowed_results = {"deleted"} if sys.argv[2] == "1" else {"deleted", "not_found"}
for entity_id in sys.argv[3:]:
    payload = json.loads((Path(sys.argv[1]) / f"opensearch-delete-{entity_id}.json").read_text(encoding="utf-8"))
    if payload.get("result") not in allowed_results:
        raise SystemExit("MCP acceptance fixture was not present in OpenSearch during cleanup")
PY
  then
    cleanup_errors=1
  fi
  if ! "${compose[@]}" exec -T postgres psql -X -q -U "$pg_user" -d "$pg_db" -v ON_ERROR_STOP=1 \
    -c "ALTER TABLE development_program_targets DISABLE TRIGGER immutable_development_program_targets; \
        DELETE FROM development_program_targets WHERE tenant_id = '$fixture_tenant_id' AND program_id IN ('$fixture_program_id_a', '$fixture_program_id_b'); \
        ALTER TABLE development_program_targets ENABLE TRIGGER immutable_development_program_targets" \
    >/dev/null; then
    cleanup_errors=1
    "${compose[@]}" exec -T postgres psql -X -q -U "$pg_user" -d "$pg_db" -v ON_ERROR_STOP=1 \
      -c "ALTER TABLE development_program_targets ENABLE TRIGGER immutable_development_program_targets" \
      >/dev/null || cleanup_errors=1
  fi
  programs_deleted=$("${compose[@]}" exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -At -v ON_ERROR_STOP=1 \
    -c "WITH deleted AS (DELETE FROM development_programs WHERE tenant_id = '$fixture_tenant_id' AND id IN ('$fixture_program_id_a', '$fixture_program_id_b') AND status_detail = 'mcp_interoperability' RETURNING 1) SELECT count(*) FROM deleted") || cleanup_errors=1
  database_deleted=$("${compose[@]}" exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -At -v ON_ERROR_STOP=1 \
    -c "WITH deleted AS (DELETE FROM entities WHERE tenant_id = '$fixture_tenant_id' AND id IN ('$fixture_target_id_a', '$fixture_target_id_b', '$fixture_drug_id_a', '$fixture_drug_id_b') AND attributes ->> 'acceptance_fixture_kind' = 'mcp_interoperability' RETURNING 1) SELECT count(*) FROM deleted") || cleanup_errors=1
  database_remaining=$("${compose[@]}" exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -At -v ON_ERROR_STOP=1 \
    -c "SELECT (SELECT count(*) FROM development_program_targets WHERE tenant_id = '$fixture_tenant_id' AND program_id IN ('$fixture_program_id_a', '$fixture_program_id_b')) + (SELECT count(*) FROM development_programs WHERE tenant_id = '$fixture_tenant_id' AND id IN ('$fixture_program_id_a', '$fixture_program_id_b')) + (SELECT count(*) FROM entities WHERE tenant_id = '$fixture_tenant_id' AND id IN ('$fixture_target_id_a', '$fixture_target_id_b', '$fixture_drug_id_a', '$fixture_drug_id_b'))") || cleanup_errors=1
  if [[ $require_present -eq 1 ]]; then
    [[ "$programs_deleted" == "2" ]] || cleanup_errors=1
    [[ "$database_deleted" == "4" ]] || cleanup_errors=1
  else
    [[ "$programs_deleted" =~ ^[0-2]$ ]] || cleanup_errors=1
    [[ "$database_deleted" =~ ^[0-4]$ ]] || cleanup_errors=1
  fi
  [[ "$database_remaining" == "0" ]] || cleanup_errors=1
  for fixture_target_id in "$fixture_target_id_a" "$fixture_target_id_b"; do
    opensearch_status=$(curl --disable --silent --show-error \
      "http://127.0.0.1:9200/$opensearch_index_prefix-entities-read/_doc/$fixture_tenant_id:$fixture_target_id?routing=$fixture_tenant_id" \
      --output /dev/null \
      --write-out '%{http_code}') || cleanup_errors=1
    [[ "$opensearch_status" == "404" ]] || cleanup_errors=1
  done
  if [[ $cleanup_errors -ne 0 ]]; then
    return 1
  fi
  rm -rf -- "$fixture_root"
  fixture_enabled=0
}

cleanup_local_commercial_fixture() {
  local commercial_client_id=""
  local commercial_subscription_id=""
  local commercial_account_id=""
  local commercial_rate_card_id=""
  local commercial_credit_grant_id=""
  local commercial_remaining=""
  commercial_client_id=$("${compose[@]}" exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -At -v ON_ERROR_STOP=1 \
    -c "SELECT id FROM agent_clients WHERE tenant_id = '$fixture_tenant_id' AND client_key = '$commercial_client_key'") || return 1
  commercial_subscription_id=$("${compose[@]}" exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -At -v ON_ERROR_STOP=1 \
    -c "SELECT id FROM commercial_subscriptions WHERE tenant_id = '$fixture_tenant_id' AND subscription_key = '$commercial_subscription_key'") || return 1
  commercial_account_id=$("${compose[@]}" exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -At -v ON_ERROR_STOP=1 \
    -c "SELECT id FROM billing_accounts WHERE tenant_id = '$fixture_tenant_id' AND account_key = '$commercial_account_key'") || return 1
  commercial_rate_card_id=$("${compose[@]}" exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -At -v ON_ERROR_STOP=1 \
    -c "SELECT id FROM rate_card_versions WHERE tenant_id = '$fixture_tenant_id' AND rate_card_key = '$commercial_rate_card_key'") || return 1
  commercial_credit_grant_id=$("${compose[@]}" exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -At -v ON_ERROR_STOP=1 \
    -c "SELECT id FROM credit_grants WHERE tenant_id = '$fixture_tenant_id' AND external_reference = '$commercial_credit_reference'") || return 1
  [[ -z "$commercial_client_id" || "$commercial_client_id" =~ ^[0-9a-f-]{36}$ ]] || return 1
  [[ -z "$commercial_subscription_id" || "$commercial_subscription_id" =~ ^[0-9a-f-]{36}$ ]] || return 1
  [[ -z "$commercial_account_id" || "$commercial_account_id" =~ ^[0-9a-f-]{36}$ ]] || return 1
  [[ -z "$commercial_rate_card_id" || "$commercial_rate_card_id" =~ ^[0-9a-f-]{36}$ ]] || return 1
  [[ -z "$commercial_credit_grant_id" || "$commercial_credit_grant_id" =~ ^[0-9a-f-]{36}$ ]] || return 1
  local immutable_tables=(
    credit_grants usage_events usage_settlements commercial_ledger_entries rate_card_items
    rate_card_versions commercial_coverage_records commercial_policy_events
    commercial_reconciliation_runs billing_adjustments billing_period_statements
  )
  local disable_sql=""
  local enable_sql=""
  local table=""
  for table in "${immutable_tables[@]}"; do
    disable_sql+="ALTER TABLE $table DISABLE TRIGGER immutable_commercial_history; "
    enable_sql="ALTER TABLE $table ENABLE TRIGGER immutable_commercial_history; $enable_sql"
  done
  disable_sql+="ALTER TABLE billing_dispute_events DISABLE TRIGGER immutable_billing_dispute_history; "
  enable_sql="ALTER TABLE billing_dispute_events ENABLE TRIGGER immutable_billing_dispute_history; $enable_sql"
  if ! "${compose[@]}" exec -T postgres psql -X -q -U "$pg_user" -d "$pg_db" -v ON_ERROR_STOP=1 \
    -c "$disable_sql
      DELETE FROM billing_dispute_events WHERE dispute_id IN (SELECT id FROM billing_disputes WHERE tenant_id = '$fixture_tenant_id' AND subscription_id = '$commercial_subscription_id');
      DELETE FROM commercial_risk_cases WHERE policy_event_id IN (SELECT id FROM commercial_policy_events WHERE tenant_id = '$fixture_tenant_id' AND subscription_id = '$commercial_subscription_id');
      DELETE FROM commercial_coverage_records WHERE tenant_id = '$fixture_tenant_id' AND subscription_id = '$commercial_subscription_id';
      DELETE FROM commercial_ledger_entries WHERE tenant_id = '$fixture_tenant_id' AND subscription_id = '$commercial_subscription_id';
      DELETE FROM billing_adjustments WHERE tenant_id = '$fixture_tenant_id' AND subscription_id = '$commercial_subscription_id';
      DELETE FROM usage_settlements WHERE tenant_id = '$fixture_tenant_id' AND subscription_id = '$commercial_subscription_id';
      DELETE FROM usage_events WHERE tenant_id = '$fixture_tenant_id' AND subscription_id = '$commercial_subscription_id';
      DELETE FROM commercial_policy_events WHERE tenant_id = '$fixture_tenant_id' AND subscription_id = '$commercial_subscription_id';
      DELETE FROM data_export_jobs WHERE tenant_id = '$fixture_tenant_id' AND subscription_id = '$commercial_subscription_id';
      DELETE FROM invoice_references WHERE tenant_id = '$fixture_tenant_id' AND billing_account_id = '$commercial_account_id';
      DELETE FROM billing_disputes WHERE tenant_id = '$fixture_tenant_id' AND subscription_id = '$commercial_subscription_id';
      DELETE FROM commercial_reconciliation_runs WHERE tenant_id = '$fixture_tenant_id' AND subscription_id = '$commercial_subscription_id';
      DELETE FROM billing_period_statements WHERE tenant_id = '$fixture_tenant_id' AND subscription_id = '$commercial_subscription_id';
      DELETE FROM credit_grants WHERE tenant_id = '$fixture_tenant_id' AND subscription_id = '$commercial_subscription_id';
      DELETE FROM commercial_entitlements WHERE tenant_id = '$fixture_tenant_id' AND subscription_id = '$commercial_subscription_id';
      DELETE FROM usage_reservations WHERE tenant_id = '$fixture_tenant_id' AND subscription_id = '$commercial_subscription_id';
      DELETE FROM commercial_subscriptions WHERE id = '$commercial_subscription_id';
      DELETE FROM commercial_export_policies WHERE tenant_id = '$fixture_tenant_id' AND billing_account_id = '$commercial_account_id';
      DELETE FROM commercial_risk_policies WHERE tenant_id = '$fixture_tenant_id' AND billing_account_id = '$commercial_account_id';
      DELETE FROM agent_client_subjects WHERE tenant_id = '$fixture_tenant_id' AND agent_client_id = '$commercial_client_id';
      DELETE FROM rate_card_items WHERE tenant_id = '$fixture_tenant_id' AND rate_card_version_id = '$commercial_rate_card_id';
      DELETE FROM rate_card_versions WHERE id = '$commercial_rate_card_id';
      DELETE FROM billing_accounts WHERE id = '$commercial_account_id';
      DELETE FROM agent_clients WHERE id = '$commercial_client_id';
      DELETE FROM audit_events WHERE tenant_id = '$fixture_tenant_id' AND actor_id = '$commercial_actor_id';
      DELETE FROM outbox_events WHERE tenant_id = '$fixture_tenant_id' AND aggregate_id IN ('$commercial_client_id', '$commercial_subscription_id', '$commercial_rate_card_id', '$commercial_account_id', '$commercial_credit_grant_id');
      $enable_sql" >/dev/null; then
    return 1
  fi
  commercial_remaining=$("${compose[@]}" exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -At -v ON_ERROR_STOP=1 \
    -c "SELECT
      (SELECT count(*) FROM agent_clients WHERE id = '$commercial_client_id') +
      (SELECT count(*) FROM commercial_subscriptions WHERE id = '$commercial_subscription_id') +
      (SELECT count(*) FROM billing_accounts WHERE id = '$commercial_account_id') +
      (SELECT count(*) FROM rate_card_versions WHERE id = '$commercial_rate_card_id') +
      (SELECT count(*) FROM credit_grants WHERE id = '$commercial_credit_grant_id') +
      (SELECT count(*) FROM usage_reservations WHERE subscription_id = '$commercial_subscription_id') +
      (SELECT count(*) FROM usage_events WHERE subscription_id = '$commercial_subscription_id') +
      (SELECT count(*) FROM usage_settlements WHERE subscription_id = '$commercial_subscription_id') +
      (SELECT count(*) FROM commercial_ledger_entries WHERE subscription_id = '$commercial_subscription_id')") || return 1
  [[ "$commercial_remaining" == "0" ]]
}

cleanup_local_fixture() {
  status=$?
  trap - EXIT INT TERM
  set +e
  remove_local_fixture 0
  exit "$status"
}

if [[ "$mcp_url" == "http://127.0.0.1:18390/mcp" ]]; then
  for command in curl docker; do
    command -v "$command" >/dev/null 2>&1 || {
      echo "required local runtime command is unavailable: $command" >&2
      exit 1
    }
  done
  token_prefix=${TEST_MCP_ACCESS_TOKEN:0:12}
  [[ "$token_prefix" =~ ^[A-Za-z0-9_-]{8,16}$ ]] || {
    echo "Local MCP acceptance token does not expose a safe API key prefix" >&2
    exit 1
  }
  commercial_suffix="${token_prefix,,}"
  commercial_suffix="${commercial_suffix//[^a-z0-9]/}"
  commercial_client_key="mcp-interoperability-${commercial_suffix}-client"
  commercial_account_key="mcp-interoperability-${commercial_suffix}-account"
  commercial_subscription_key="mcp-interoperability-${commercial_suffix}-subscription"
  commercial_rate_card_key="mcp-interoperability-${commercial_suffix}-plan"
  commercial_credit_reference="mcp-interoperability-${commercial_suffix}-credit"
  commercial_actor_id="mcp-interoperability-${commercial_suffix}"
  pg_user=$("${compose[@]}" exec -T postgres printenv POSTGRES_USER | tr -d '\r')
  pg_db=$("${compose[@]}" exec -T postgres printenv POSTGRES_DB | tr -d '\r')
  fixture_tenant_id=$(
    "${compose[@]}" exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -At -v ON_ERROR_STOP=1 \
      -c "SELECT tenant_id FROM api_keys WHERE prefix = '$token_prefix' AND active IS TRUE AND revoked_at IS NULL"
  )
  [[ "$fixture_tenant_id" =~ ^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$ ]] || {
    echo "Local MCP acceptance token did not resolve to exactly one active tenant" >&2
    exit 1
  }
  opensearch_index_prefix=$(
    "${compose[@]}" exec -T worker sh -ec 'printf %s "${OPENSEARCH_INDEX_PREFIX:-pharma}"'
  )
  [[ "$opensearch_index_prefix" =~ ^[a-z0-9][a-z0-9-]{0,79}$ ]] || {
    echo "Runtime returned an unsafe OpenSearch index prefix" >&2
    exit 1
  }
  fixture_target_id_a=$(python3 -c 'import uuid; print(uuid.uuid4())')
  fixture_target_id_b=$(python3 -c 'import uuid; print(uuid.uuid4())')
  fixture_drug_id_a=$(python3 -c 'import uuid; print(uuid.uuid4())')
  fixture_drug_id_b=$(python3 -c 'import uuid; print(uuid.uuid4())')
  fixture_program_id_a=$(python3 -c 'import uuid; print(uuid.uuid4())')
  fixture_program_id_b=$(python3 -c 'import uuid; print(uuid.uuid4())')
  acceptance_query="mcp-${fixture_target_id_a:0:12}"
  fixture_root=$(mktemp -d -t pharma-mcp-interoperability-fixture.XXXXXX)
  fixture_enabled=1
  trap cleanup_local_fixture EXIT INT TERM
  if [[ $seed_local_commercial_fixture -eq 1 ]]; then
    commercial_fixture_enabled=1
    "${compose[@]}" exec -T api python -m pharma_intel.mcp_interoperability_fixture seed \
      --api-key-prefix "$token_prefix" >/dev/null
  fi
  "${compose[@]}" exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -v ON_ERROR_STOP=1 \
    -c "INSERT INTO entities (id, tenant_id, entity_type, name, normalized_name, description, external_ids, attributes, review_status, created_at, updated_at) VALUES
      ('$fixture_target_id_a', '$fixture_tenant_id', 'TARGET', 'MCP interoperability $acceptance_query Alpha', 'mcp interoperability $acceptance_query alpha', 'Isolated MCP interoperability target fixture Alpha', '{\"acceptance\": \"$acceptance_query\"}'::json, '{\"acceptance_fixture\": true, \"acceptance_fixture_kind\": \"mcp_interoperability\"}'::json, 'DRAFT', now(), now()),
      ('$fixture_target_id_b', '$fixture_tenant_id', 'TARGET', 'MCP interoperability $acceptance_query Beta', 'mcp interoperability $acceptance_query beta', 'Isolated MCP interoperability target fixture Beta', '{\"acceptance\": \"$acceptance_query\"}'::json, '{\"acceptance_fixture\": true, \"acceptance_fixture_kind\": \"mcp_interoperability\"}'::json, 'DRAFT', now(), now()),
      ('$fixture_drug_id_a', '$fixture_tenant_id', 'DRUG', 'MCP candidate $acceptance_query Alpha', 'mcp candidate $acceptance_query alpha', 'Isolated MCP competitive drug fixture Alpha', '{}'::json, '{\"acceptance_fixture\": true, \"acceptance_fixture_kind\": \"mcp_interoperability\"}'::json, 'DRAFT', now(), now()),
      ('$fixture_drug_id_b', '$fixture_tenant_id', 'DRUG', 'MCP candidate $acceptance_query Beta', 'mcp candidate $acceptance_query beta', 'Isolated MCP competitive drug fixture Beta', '{}'::json, '{\"acceptance_fixture\": true, \"acceptance_fixture_kind\": \"mcp_interoperability\"}'::json, 'DRAFT', now(), now());
      INSERT INTO development_programs (
        id, tenant_id, drug_entity_id, target_entity_id, modality, mechanism_of_action, phase,
        status_date, geography, status_detail, global_phase, china_phase,
        global_phase_started_at, china_phase_started_at, development_rights_regions,
        commercialization_rights_regions, program_tags, target_set_version, organization_set_version,
        target_combination_key, milestones, created_at, updated_at
      ) VALUES
      ('$fixture_program_id_a', '$fixture_tenant_id', '$fixture_drug_id_a', '$fixture_target_id_a', 'small molecule', 'acceptance inhibitor', 'PHASE_2', now(), 'global', 'mcp_interoperability', 'phase_2', 'phase_1', '2026-06-01T00:00:00Z', '2025-03-01T00:00:00Z', '[\"Global\"]'::json, '[\"Greater China\"]'::json, '[\"first_in_class\"]'::json, 1, 1, least('$fixture_target_id_a', '$fixture_target_id_b') || '|' || greatest('$fixture_target_id_a', '$fixture_target_id_b'), '[{\"milestone_type\":\"first_patient_in\",\"title\":\"MCP first patient in\",\"occurred_at\":\"2026-06-15T00:00:00+00:00\"}]'::json, now(), now()),
      ('$fixture_program_id_b', '$fixture_tenant_id', '$fixture_drug_id_b', '$fixture_target_id_b', 'antibody', 'acceptance antagonist', 'PHASE_1', now(), 'global', 'mcp_interoperability', 'phase_1', NULL, '2025-01-01T00:00:00Z', NULL, '[\"US\"]'::json, '[]'::json, '[]'::json, 1, 1, '$fixture_target_id_b', '[]'::json, now(), now());
      INSERT INTO development_program_targets (
        id, tenant_id, program_id, target_set_version, target_entity_id, role, position,
        created_at, updated_at
      ) VALUES
      (gen_random_uuid(), '$fixture_tenant_id', '$fixture_program_id_a', 1, '$fixture_target_id_a', 'primary', 0, now(), now()),
      (gen_random_uuid(), '$fixture_tenant_id', '$fixture_program_id_a', 1, '$fixture_target_id_b', 'combination', 1, now(), now()),
      (gen_random_uuid(), '$fixture_tenant_id', '$fixture_program_id_b', 1, '$fixture_target_id_b', 'primary', 0, now(), now())" \
    >/dev/null
  python3 - "$fixture_root" "$fixture_tenant_id" "$fixture_target_id_a" "$fixture_target_id_b" "$acceptance_query" <<'PY'
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

root, tenant_id, target_a, target_b, query = sys.argv[1:]
for entity_id, suffix in ((target_a, "Alpha"), (target_b, "Beta")):
    payload = {
        "schema_version": 1,
        "tenant_id": tenant_id,
        "entity_id": entity_id,
        "entity_type": "target",
        "name": f"MCP interoperability {query} {suffix}",
        "normalized_name": f"mcp interoperability {query} {suffix.lower()}",
        "aliases": [],
        "description": f"Isolated MCP interoperability target fixture {suffix}",
        "external_id_values": [query],
        "external_ids": {"acceptance": query},
        "review_status": "draft",
        "updated_at": datetime.now(UTC).isoformat(),
    }
    (Path(root) / f"entity-{entity_id}.json").write_text(
        json.dumps(payload, separators=(",", ":")),
        encoding="utf-8",
    )
PY
  for fixture_target_id in "$fixture_target_id_a" "$fixture_target_id_b"; do
    curl --disable --fail --silent --show-error --request PUT \
      "http://127.0.0.1:9200/$opensearch_index_prefix-entities-write/_doc/$fixture_tenant_id:$fixture_target_id?routing=$fixture_tenant_id&refresh=true" \
      --header 'Content-Type: application/json' \
      --data-binary "@$fixture_root/entity-$fixture_target_id.json" \
      --output "$fixture_root/opensearch-index-$fixture_target_id.json"
  done
elif [[ -z "$acceptance_query" ]]; then
  echo "MCP_ACCEPTANCE_QUERY is required for a non-local MCP endpoint" >&2
  exit 1
fi

inspector_result=$(
  cd "$root"
  "$uv_path" run python -m scripts.mcp_inspector_probe \
    --node "$node_path" \
    --cli "$package" \
    --url "$mcp_url" \
    --query "$acceptance_query"
)
result=$(
  cd "$root"
  "$uv_path" run python -m scripts.mcp_sdk_probe \
    --url "$mcp_url" \
    --query "$acceptance_query" \
    --expected-sdk-version "$sdk_version" \
    --expected-protocol-version "$protocol_baseline" \
    --inspector-result-json "$inspector_result"
)
remove_local_fixture 1
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
    echo "refusing to overwrite MCP interoperability evidence: $output_path" >&2
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
        *) echo "refusing to clean unexpected MCP interoperability evidence path: $temporary" >&2 ;;
      esac
    fi
    return "$status"
  }
  trap cleanup_output EXIT
  trap 'exit 130' INT
  trap 'exit 143' TERM
  printf '%s\n' "$result" > "$temporary"
  python3 - "$temporary" "$version" <<'PY'
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

path = Path(sys.argv[1])
document = json.loads(path.read_text(encoding="utf-8"))
document["inspector_version"] = sys.argv[2]
document["created_at"] = datetime.now(UTC).isoformat()
path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
  chmod 600 "$temporary"
  mv -- "$temporary" "$output_path"
  output_complete=1
  trap - EXIT INT TERM
  printf 'mcp_interoperability_report=%s\n' "$output_path"
fi

printf 'mcp_interoperability_status=passed\n'
printf 'inspector_version=%s\n' "$version"
printf 'python_sdk_version=%s\n' "$sdk_version"
printf 'protocol_baseline=%s\n' "$protocol_baseline"
