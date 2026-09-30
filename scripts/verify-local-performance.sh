#!/usr/bin/env bash
set -Eeuo pipefail

umask 077

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
web_url="http://127.0.0.1:18380"
mcp_url="http://127.0.0.1:18390/mcp"
output_path=""

usage() {
  cat <<'EOF'
Usage: verify-local-performance.sh [options]

Run a bounded local mixed Web/MCP performance baseline with an isolated human
account in the MCP token tenant. This is Development/Pilot evidence only.

Options:
  --web-url URL    Human Web/API origin (default: http://127.0.0.1:18380).
  --mcp-url URL    MCP endpoint (default: http://127.0.0.1:18390/mcp).
  --output FILE    Write an exclusive, private machine-readable report.
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

[[ -n "${TEST_MCP_ACCESS_TOKEN:-}" ]] || { echo "TEST_MCP_ACCESS_TOKEN is required" >&2; exit 1; }
for command in awk docker openssl python3 realpath uv; do
  command -v "$command" >/dev/null 2>&1 || { echo "required command is unavailable: $command" >&2; exit 1; }
done
for url in "$web_url" "$mcp_url"; do
  case "$url" in
    http://*|https://*) ;;
    *) echo "entry URLs must use HTTP or HTTPS" >&2; exit 2 ;;
  esac
done

export COMPOSE_FILE="${COMPOSE_FILE:-compose.yaml:compose.dev.yaml:compose.telemetry.yaml}"
cd "$root"
pg_user=$(docker compose exec -T postgres printenv POSTGRES_USER | tr -d '\r')
pg_db=$(docker compose exec -T postgres printenv POSTGRES_DB | tr -d '\r')
token_prefix=${TEST_MCP_ACCESS_TOKEN:0:12}
[[ "$token_prefix" =~ ^[A-Za-z0-9_-]{8,16}$ ]] || { echo "MCP token has an unsafe key prefix" >&2; exit 1; }
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

stale_users=$(docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -At -v ON_ERROR_STOP=1 \
  -c "SELECT count(*) FROM users WHERE normalized_email LIKE 'performance-%@example.test'")
[[ "$stale_users" == "0" ]] || { echo "Refusing to run with stale performance users" >&2; exit 1; }

marker="performance-$(python3 -c 'import uuid; print(uuid.uuid4().hex[:16])')"
email="$marker@example.test"
password="$(openssl rand -hex 24)Aa1!"
temporary_root=$(mktemp -d -t pharma-performance.XXXXXX)
raw_report="$temporary_root/report.json"
account_active=1

remove_account() {
  local cleanup_errors=0
  [[ $account_active -eq 1 ]] || return 0
  deleted=$(docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -At -v ON_ERROR_STOP=1 \
    -c "DELETE FROM users WHERE tenant_id = '$tenant_id' AND normalized_email = '$email' RETURNING id") || cleanup_errors=1
  [[ $(printf '%s\n' "$deleted" | awk '/^[0-9a-f-]{36}$/ { count += 1 } END { print count + 0 }') == "1" ]] || cleanup_errors=1
  remaining=$(docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -At -v ON_ERROR_STOP=1 \
    -c "SELECT count(*) FROM users WHERE normalized_email = '$email'") || cleanup_errors=1
  [[ "$remaining" == "0" ]] || cleanup_errors=1
  account_active=0
  [[ $cleanup_errors -eq 0 ]]
}

cleanup_on_exit() {
  status=$?
  trap - EXIT INT TERM
  set +e
  remove_account
  if [[ "$temporary_root" == /tmp/pharma-performance.* ]]; then
    find "$temporary_root" -mindepth 1 -delete
    rmdir -- "$temporary_root"
  fi
  exit "$status"
}
trap cleanup_on_exit EXIT INT TERM

docker compose run --rm --no-deps migrate pharma-bootstrap \
  --tenant-slug "$tenant_slug" \
  --tenant-name "Performance Acceptance" \
  --skip-api-key \
  --admin-email "$email" \
  --admin-password "$password" \
  --admin-name "Performance Acceptance" >/dev/null
viewer_role=$(docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -At -v ON_ERROR_STOP=1 \
  -c "UPDATE users SET role = 'VIEWER' WHERE tenant_id = '$tenant_id' AND normalized_email = '$email' RETURNING role")
[[ $(printf '%s\n' "$viewer_role" | awk '$0 == "VIEWER" { count += 1 } END { print count + 0 }') == "1" ]] || {
  echo "performance account was not reduced to the viewer role" >&2
  exit 1
}

if ! PERFORMANCE_TEST_EMAIL="$email" PERFORMANCE_TEST_PASSWORD="$password" \
  uv run pharma-performance-load --web-url "$web_url" --mcp-url "$mcp_url" > "$raw_report"; then
  echo "performance load command failed" >&2
  python3 - "$raw_report" <<'PY' >&2
import sys
from pathlib import Path

payload = Path(sys.argv[1]).read_bytes()
if len(payload) > 65_536:
    raise SystemExit("performance failure report exceeded 65536 bytes")
sys.stderr.write(payload.decode("utf-8", errors="replace"))
if payload and not payload.endswith(b"\n"):
    sys.stderr.write("\n")
PY
  exit 1
fi
remove_account

python3 - "$raw_report" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
report = json.loads(path.read_text(encoding="utf-8"))
if report.get("status") != "passed" or report.get("production_claim") is not False:
    raise SystemExit("local performance report did not pass")
report["temporary_users_after"] = 0
report["temporary_human_role"] = "viewer"
path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
path.chmod(0o600)
PY

if [[ -n "$output_path" ]]; then
  output_parent=$(dirname -- "$output_path")
  output_name=$(basename -- "$output_path")
  [[ "$output_name" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]] || { echo "invalid output filename" >&2; exit 2; }
  mkdir -p "$output_parent"
  output_parent=$(realpath "$output_parent")
  output_path="$output_parent/$output_name"
  [[ ! -e "$output_path" && ! -L "$output_path" ]] || { echo "refusing to overwrite performance evidence" >&2; exit 1; }
  python3 - "$raw_report" "$output_path" <<'PY'
import os
import sys
import tempfile
from pathlib import Path

source = Path(sys.argv[1])
target = Path(sys.argv[2])
descriptor, name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
temporary = Path(name)
try:
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(source.read_bytes())
        handle.flush()
        os.fsync(handle.fileno())
    temporary.chmod(0o600)
    os.link(temporary, target, follow_symlinks=False)
finally:
    temporary.unlink(missing_ok=True)
PY
  printf 'performance_report=%s\n' "$output_path"
fi

cat "$raw_report"
if [[ "$temporary_root" == /tmp/pharma-performance.* ]]; then
  find "$temporary_root" -mindepth 1 -delete
  rmdir -- "$temporary_root"
fi
trap - EXIT INT TERM
printf 'performance_status=passed production_claim=false\n'
