#!/usr/bin/env bash
set -euo pipefail

umask 077

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$root"
output_path=""
started_epoch=$(date +%s)

usage() {
  cat <<'EOF'
Usage: verify-local-database.sh [--output FILE]

Verify the live WSL PostgreSQL/RDKit authority, tenant RLS, migration state,
and rebuildable OpenSearch projection. The report contains no credentials.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --output)
      [[ $# -ge 2 ]] || { echo "--output requires a value" >&2; exit 2; }
      output_path=$2
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

for command in docker python3 sed realpath dirname basename mktemp uv grep; do
  command -v "$command" >/dev/null 2>&1 || {
    echo "required command is unavailable: $command" >&2
    exit 1
  }
done

compose=(docker compose -f compose.yaml -f compose.dev.yaml -f compose.telemetry.yaml)
for service in api worker postgres opensearch; do
  container=$("${compose[@]}" ps -q "$service")
  [[ -n "$container" && "$(docker inspect --format '{{.State.Running}}' "$container")" == true ]] || {
    echo "required Compose service is not running: $service" >&2
    exit 1
  }
done

work=$(mktemp -d -t pharma-database-acceptance.XXXXXX)
cleanup() {
  case "$work" in
    /tmp/pharma-database-acceptance.*) rm -rf -- "$work" ;;
    *) echo "refusing to clean unexpected database acceptance workspace: $work" >&2 ;;
  esac
}
trap cleanup EXIT INT TERM

migration_heads=$("${compose[@]}" exec -T api alembic heads)
expected_head=$(printf '%s\n' "$migration_heads" | sed -n 's/^\([0-9a-f][0-9a-f]*\) (head)$/\1/p')
[[ -n "$expected_head" && "$(printf '%s\n' "$expected_head" | wc -l)" == 1 ]] || {
  echo "Alembic must expose exactly one migration head" >&2
  exit 1
}
"${compose[@]}" exec -T api alembic check >/dev/null

pg_user=$("${compose[@]}" exec -T postgres printenv POSTGRES_USER | tr -d '\r')
pg_db=$("${compose[@]}" exec -T postgres printenv POSTGRES_DB | tr -d '\r')
[[ "$pg_user" =~ ^[a-z_][a-z0-9_]*$ && "$pg_db" =~ ^[a-z_][a-z0-9_]*$ ]] || {
  echo "unsafe PostgreSQL identity returned by the runtime" >&2
  exit 1
}
database_record=$(
  "${compose[@]}" exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -At -F '|' \
    -v ON_ERROR_STOP=1 \
    -c "SELECT current_setting('server_version'), (SELECT extversion FROM pg_extension WHERE extname = 'rdkit'), (SELECT version_num FROM alembic_version)"
)
IFS='|' read -r postgres_version rdkit_version current_head <<< "$database_record"
[[ -n "$postgres_version" && -n "$rdkit_version" && "$current_head" == "$expected_head" ]] || {
  echo "database version or Alembic head verification failed" >&2
  exit 1
}

"${compose[@]}" exec -T api pharma-verify-rls > "$work/rls.json"
"${compose[@]}" exec -T worker pharma-search status > "$work/search.json"
"${compose[@]}" exec -T api pharma-runtime-hygiene > "$work/hygiene.json"
TEST_OPENSEARCH_URL=http://127.0.0.1:9200 \
  uv run pytest -q tests/test_opensearch_integration.py -m integration > "$work/hybrid-search.txt"
grep -q "1 passed" "$work/hybrid-search.txt" || {
  echo "real OpenSearch hybrid integration test did not pass" >&2
  exit 1
}
chmod 600 "$work/rls.json" "$work/search.json" "$work/hygiene.json" "$work/hybrid-search.txt"

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

duration_seconds=$(( $(date +%s) - started_epoch ))
python3 - "$work/rls.json" "$work/search.json" "$work/hygiene.json" "$output_path" \
  "$postgres_version" "$rdkit_version" "$current_head" "$duration_seconds" <<'PY'
from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

rls_path, search_path, hygiene_path, output_text, postgres_version, rdkit_version, alembic_head, duration = sys.argv[1:]
rls = json.loads(Path(rls_path).read_text(encoding="utf-8"))
search = json.loads(Path(search_path).read_text(encoding="utf-8"))
hygiene = json.loads(Path(hygiene_path).read_text(encoding="utf-8"))
cluster = search.get("cluster")
deliveries = search.get("deliveries")
if not isinstance(rls, dict) or rls.get("passed") is not True:
    raise SystemExit("signed tenant RLS verification did not pass")
if (
    rls.get("superuser") is not False
    or rls.get("bypass_rls") is not False
    or rls.get("no_context_rows") != 0
    or rls.get("forged_context_rows") != 0
    or rls.get("signed_context_valid") is not True
):
    raise SystemExit("tenant RLS result violates the production isolation contract")
if not isinstance(cluster, dict) or cluster.get("available") is not True or cluster.get("cluster_status") != "green":
    raise SystemExit("OpenSearch projection is unavailable or not green")
if not isinstance(deliveries, dict) or any(deliveries.get(name) != 0 for name in ("dead", "retry", "processing")):
    raise SystemExit("OpenSearch projection delivery queue is not drained")
if not isinstance(hygiene, dict) or hygiene.get("status") != "passed" or hygiene.get("finding_count") != 0:
    raise SystemExit("persistent runtime contains synthetic or orphaned acceptance state")

report = {
    "schema": "pharma.local-database-acceptance.v1",
    "schema_version": 1,
    "generated_at": datetime.now(UTC).isoformat(),
    "status": "passed",
    "environment": "local-wsl",
    "production_claim": False,
    "credentials_recorded": False,
    "database": {
        "postgresql_version": postgres_version,
        "rdkit_version": rdkit_version,
        "alembic_head": alembic_head,
        "migration_drift": False,
    },
    "rls": rls,
    "runtime_hygiene": hygiene,
    "search": {"cluster": cluster, "deliveries": deliveries},
    "hybrid_search": {
        "status": "passed",
        "protocol": "OpenSearch 3.x native hybrid query and normalization pipeline",
        "index_schema_version": 2,
        "embedding_fixture": "deterministic-controlled-test-vector",
        "production_embedding_model_verified": False,
    },
    "duration_seconds": int(duration),
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
            raise SystemExit(f"refusing to overwrite database evidence: {output}") from exc
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
  printf 'database_report=%s\n' "$output_path"
fi
