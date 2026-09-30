#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/status.sh [--output PATH]

Verifies the complete local runtime and optionally writes a private,
machine-verifiable Development acceptance report.

Environment:
  PHARMA_DOCKER_COMMAND_TIMEOUT_SECONDS  Per-command Docker timeout (1-300, default: 15).
EOF
}

output_path=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --output)
      [[ $# -ge 2 && -n "$2" ]] || { usage >&2; exit 2; }
      output_path=$2
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      usage >&2
      exit 2
      ;;
  esac
done

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
started_epoch=$(date +%s)
docker_command_timeout_seconds="${PHARMA_DOCKER_COMMAND_TIMEOUT_SECONDS:-15}"
if [[ ! "$docker_command_timeout_seconds" =~ ^[0-9]+$ ]] ||
  (( docker_command_timeout_seconds < 1 || docker_command_timeout_seconds > 300 )); then
  echo "PHARMA_DOCKER_COMMAND_TIMEOUT_SECONDS must be an integer between 1 and 300" >&2
  exit 2
fi
for required_command in docker timeout; do
  command -v "$required_command" >/dev/null 2>&1 || {
    echo "required command is unavailable: $required_command" >&2
    exit 127
  }
done

docker_with_timeout() {
  local status
  if timeout --signal=TERM --kill-after=5s "${docker_command_timeout_seconds}s" docker "$@"; then
    return 0
  else
    status=$?
  fi
  if [[ "$status" == 124 || "$status" == 137 ]]; then
    printf 'Docker command exceeded the %s-second management timeout: docker' \
      "$docker_command_timeout_seconds" >&2
    printf ' %q' "$@" >&2
    printf '\n' >&2
  fi
  return "$status"
}

if docker_server_version="$(docker_with_timeout version --format '{{.Server.Version}}' 2>&1)"; then
  :
else
  cat >&2 <<EOF
Docker engine management API is unavailable or did not respond within ${docker_command_timeout_seconds} seconds.
Docker Desktop status alone is not sufficient; the Linux guest engine must answer a Docker API request.
Verify with: docker desktop status
             docker --context default version
No services were restarted and no volumes were changed by this check.
EOF
  if [[ -n "$docker_server_version" ]]; then
    printf 'Docker client detail: %s\n' "$(tr '\n' ' ' <<<"$docker_server_version")" >&2
  fi
  exit 1
fi

compose=(docker_with_timeout compose -f compose.yaml -f compose.dev.yaml -f compose.telemetry.yaml)
required_services=(
  postgres redis opensearch temporal clamav parser api worker otel-collector
)

services_ready() {
  local service container_id state health
  for service in "${required_services[@]}"; do
    container_id="$("${compose[@]}" ps --quiet "$service")"
    [[ -n "$container_id" ]] || return 1
    state="$(docker_with_timeout inspect --format '{{.State.Status}}' "$container_id")"
    [[ "$state" == running ]] || return 1
    health="$(docker_with_timeout inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$container_id")"
    if [[ "$service" == otel-collector ]]; then
      [[ "$health" == none || "$health" == healthy ]] || return 1
    else
      [[ "$health" == healthy ]] || return 1
    fi
  done
}

services_are_ready=false
services_deadline=$(( SECONDS + 120 ))
while (( SECONDS < services_deadline )); do
  if services_ready; then
    services_are_ready=true
    break
  fi
  sleep 1
done
if [[ "$services_are_ready" != true ]]; then
  echo "required runtime services did not become running and healthy within 120 seconds" >&2
  "${compose[@]}" ps >&2 || true
  exit 1
fi

echo "[runtime] compose services"
"${compose[@]}" ps

echo "[runtime] API liveness"
curl --noproxy '*' --fail --silent --show-error http://127.0.0.1:18380/health/live >/dev/null
echo "passed"

echo "[runtime] API readiness"
curl --noproxy '*' --fail --silent --show-error http://127.0.0.1:18380/health/ready >/dev/null
echo "passed"

echo "[runtime] governed human workbench routes"
workbench_status=$(python3 - <<'PY'
from __future__ import annotations

import json
import hashlib
import urllib.request


def probe(name: str, path: str, workbench: str) -> dict[str, object]:
    url = f"http://127.0.0.1:18380{path}"
    results: dict[str, object] = {"path": path}
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for method in ("GET", "HEAD"):
        request = urllib.request.Request(url, method=method)
        with opener.open(request, timeout=10) as response:
            body = response.read()
            status = response.status
            content_type = response.headers.get_content_type()
            content_security_policy = response.headers.get("Content-Security-Policy", "")
            frame_options = response.headers.get("X-Frame-Options", "")
        if status != 200:
            raise SystemExit(f"{name} {method} returned HTTP {status}")
        if content_type != "text/html":
            raise SystemExit(f"{name} {method} returned {content_type}, expected text/html")
        if "frame-ancestors 'none'" not in content_security_policy:
            raise SystemExit(f"{name} {method} is missing the fail-closed frame policy")
        if frame_options != "DENY":
            raise SystemExit(f"{name} {method} is missing X-Frame-Options: DENY")
        if method == "GET":
            if b'<div id="root"></div>' not in body:
                raise SystemExit(f"{name} GET did not return the SPA shell")
            marker = f'data-workbench="{workbench}"'.encode()
            if marker not in body:
                raise SystemExit(f"{name} GET returned the wrong workbench document")
            results["document_sha256"] = hashlib.sha256(body).hexdigest()
        if method == "HEAD" and body:
            raise SystemExit(f"{name} HEAD unexpectedly returned a response body")
        results[f"{method.lower()}_status"] = status
    results["content_type"] = "text/html"
    results["security_headers"] = "passed"
    results["spa_shell"] = "passed"
    results["entry_document"] = f"{workbench}.html"
    results["workbench_marker"] = workbench
    return results


workbenches = {
    "research": probe("research workbench", "/workspace/research", "research"),
    "internal": probe("internal workbench", "/workspace/internal", "internal"),
}
if workbenches["research"]["document_sha256"] == workbenches["internal"]["document_sha256"]:
    raise SystemExit("research and internal workbenches returned the same HTML document")
print(json.dumps(workbenches, separators=(",", ":")))
PY
)
printf '%s\n' "$workbench_status"
echo "passed"

echo "[runtime] isolated parser readiness"
"${compose[@]}" exec -T parser python -c \
  "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8070/health/ready', timeout=5)"
"${compose[@]}" exec -T worker python -c \
  "from pharma_intel.config import get_settings; assert get_settings().parser_backend == 'service'"
echo "passed"

echo "[runtime] unauthenticated MCP rejection"
mcp_status=""
for _ in {1..30}; do
  if mcp_status="$(curl --noproxy '*' --silent --output /dev/null --write-out '%{http_code}' http://127.0.0.1:18390/mcp)"; then
    break
  fi
  sleep 1
done
if [[ "$mcp_status" != 401 ]]; then
  echo "expected HTTP 401 from unauthenticated MCP, received ${mcp_status:-no response}" >&2
  exit 1
fi
echo "passed"

echo "[runtime] unified jobs process"
"${compose[@]}" exec -T worker pharma-jobs-health
jobs_pid=$("${compose[@]}" exec -T worker python -c \
  "import json,pathlib; pids={json.loads(path.read_text())['pid'] for path in pathlib.Path('/tmp/pharma-runtime-heartbeats').glob('*.json')}; assert len(pids) == 1; print(next(iter(pids)))")
[[ "$jobs_pid" =~ ^[0-9]+$ ]] || {
  echo "unified jobs heartbeat PID is invalid" >&2
  exit 1
}
printf 'passed (pid=%s)\n' "$jobs_pid"

echo "[runtime] database migration"
alembic_status=$("${compose[@]}" exec -T api alembic current 2>/dev/null)
printf '%s\n' "$alembic_status"
alembic_head=$(sed -n 's/^\([0-9a-f]\{12\}\) (head)$/\1/p' <<<"$alembic_status")
[[ "$alembic_head" =~ ^[0-9a-f]{12}$ ]] || {
  echo "runtime did not report exactly one canonical Alembic head" >&2
  exit 1
}

echo "[runtime] PostgreSQL and RDKit"
database_versions=$("${compose[@]}" exec -T postgres sh -ec '
  psql --no-psqlrc --set ON_ERROR_STOP=1 --tuples-only --no-align \
    --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
    --command "SELECT current_setting('"'"'server_version'"'"'), extversion FROM pg_extension WHERE extname = '"'"'rdkit'"'"';"
')
printf '%s\n' "$database_versions"
IFS='|' read -r postgresql_version rdkit_version <<<"$database_versions"
[[ -n "$postgresql_version" && -n "$rdkit_version" ]] || {
  echo "runtime PostgreSQL/RDKit version result is incomplete" >&2
  exit 1
}

echo "[runtime] OpenSearch projection"
search_status=$("${compose[@]}" exec -T worker pharma-search status)
printf '%s\n' "$search_status"

echo "[runtime] persistent data hygiene"
hygiene_status=$("${compose[@]}" exec -T api pharma-runtime-hygiene)
printf '%s\n' "$hygiene_status"

if [[ -n "$output_path" ]]; then
  output_parent=$(dirname -- "$output_path")
  output_name=$(basename -- "$output_path")
  [[ "$output_name" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]] || {
    echo "invalid runtime evidence filename: $output_name" >&2
    exit 2
  }
  mkdir -p "$output_parent"
  output_parent=$(realpath "$output_parent")
  output_path="$output_parent/$output_name"
  [[ ! -e "$output_path" && ! -L "$output_path" ]] || {
    echo "refusing to overwrite runtime evidence: $output_path" >&2
    exit 1
  }

  services_json="["
  separator=""
  for service in "${required_services[@]}"; do
    container_id=$("${compose[@]}" ps --quiet "$service")
    state=$(docker_with_timeout inspect --format '{{.State.Status}}' "$container_id")
    health=$(docker_with_timeout inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$container_id")
    image_id=$(docker_with_timeout inspect --format '{{.Image}}' "$container_id")
    service_json=$(python3 -c 'import json,sys; print(json.dumps({"service":sys.argv[1],"state":sys.argv[2],"health":sys.argv[3],"image_id":sys.argv[4]}, separators=(",",":")))' "$service" "$state" "$health" "$image_id")
    services_json+="$separator$service_json"
    separator=","
  done
  services_json+="]"
  duration_seconds=$(( $(date +%s) - started_epoch ))
  SERVICES_JSON="$services_json" SEARCH_JSON="$search_status" HYGIENE_JSON="$hygiene_status" \
    WORKBENCH_JSON="$workbench_status" \
    python3 - "$output_path" "$alembic_head" "$postgresql_version" "$rdkit_version" "$duration_seconds" <<'PY'
from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

output_text, alembic_head, postgresql_version, rdkit_version, duration = sys.argv[1:]
output = Path(output_text)
report = {
    "schema": "pharma.local-runtime-acceptance.v3",
    "schema_version": 3,
    "generated_at": datetime.now(UTC).isoformat(),
    "status": "passed",
    "environment": "local-wsl",
    "production_claim": False,
    "credentials_recorded": False,
    "compose_profile": "compose+dev+telemetry",
    "services": json.loads(os.environ["SERVICES_JSON"]),
    "entrypoints": {
        "web": {
            "url": "http://127.0.0.1:18380",
            "liveness": "passed",
            "readiness": "passed",
            "workbenches": json.loads(os.environ["WORKBENCH_JSON"]),
        },
        "mcp": {"url": "http://127.0.0.1:18390/mcp", "unauthenticated_status": 401},
        "parser": {"backend": "service", "readiness": "passed"},
    },
    "database": {
        "alembic_head": alembic_head,
        "postgresql_version": postgresql_version,
        "rdkit_version": rdkit_version,
    },
    "search": json.loads(os.environ["SEARCH_JSON"]),
    "runtime_hygiene": json.loads(os.environ["HYGIENE_JSON"]),
    "main_runtime_modified": False,
    "duration_seconds": int(duration),
}
payload = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode()
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
        raise SystemExit(f"refusing to overwrite runtime evidence: {output}") from exc
    directory_fd = os.open(output.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
finally:
    temporary.unlink(missing_ok=True)
print(f"runtime_report={output}")
PY
fi

echo "[runtime] all local status checks passed"
