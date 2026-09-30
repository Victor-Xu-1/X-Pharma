#!/usr/bin/env bash
set -Eeuo pipefail

umask 077
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$root"
output_path=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --output)
      [[ $# -ge 2 ]] || { echo "--output requires a value" >&2; exit 2; }
      output_path=$2
      shift 2
      ;;
    -h|--help)
      echo "Usage: verify-local-observability.sh [--output FILE]"
      exit 0
      ;;
    *)
      echo "unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

[[ -n "${TEST_MCP_ACCESS_TOKEN:-}" ]] || { echo "TEST_MCP_ACCESS_TOKEN is required" >&2; exit 1; }
for command in date docker python3 realpath uv; do
  command -v "$command" >/dev/null 2>&1 || { echo "required command is unavailable: $command" >&2; exit 1; }
done

export COMPOSE_FILE="${COMPOSE_FILE:-compose.yaml:compose.dev.yaml:compose.telemetry.yaml}"
work=$(mktemp -d -t pharma-observability.XXXXXX)
cleanup() {
  status=$?
  trap - EXIT INT TERM
  if [[ "$work" == /tmp/pharma-observability.* && -d "$work" ]]; then
    find "$work" -mindepth 1 -delete
    rmdir "$work"
  fi
  exit "$status"
}
trap cleanup EXIT INT TERM

uv run pharma-operations-verify --output "$work/contract.json" >/dev/null
docker compose up -d --force-recreate --wait --wait-timeout 60 otel-collector mcp >/dev/null
collector_id=$(docker compose ps -q otel-collector)
[[ -n "$collector_id" ]] || { echo "local Collector did not start" >&2; exit 1; }
for _ in {1..15}; do
  [[ "$(docker inspect --format '{{.State.Running}}' "$collector_id")" == "true" ]] && break
  sleep 1
done
[[ "$(docker inspect --format '{{.State.Running}}' "$collector_id")" == "true" ]] || {
  echo "local Collector is not running" >&2
  exit 1
}
started_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
uv run pharma-mcp-load \
  --requests 4 \
  --concurrency 2 \
  --max-p95-ms 2000 \
  --output "$work/load.json" >/dev/null

metrics=(
  pharma.mcp.commercial.calls
  pharma.mcp.commercial.duration
)
deadline=$((SECONDS + 30))
while true; do
  docker compose logs --since "$started_at" --no-color otel-collector \
    > "$work/collector-metrics.log"
  missing=0
  for metric in "${metrics[@]}"; do
    grep -Fq "$metric" "$work/collector-metrics.log" || missing=1
  done
  [[ $missing -eq 0 ]] && break
  (( SECONDS < deadline )) || { echo "operational metrics did not reach the local Collector" >&2; exit 1; }
  sleep 2
done

OBSERVED_METRICS=$(IFS=,; printf '%s' "${metrics[*]}") \
  python3 - "$work/contract.json" "$work/load.json" "$work/report.json" <<'PY'
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

contract = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
load = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
assert contract["status"] == "passed"
assert load["requests"]["completed"] == 4
assert load["requests"]["failed"] == 0
assert load["billing"]["unique_settlement_ids"] == 4
assert load["billing"]["active_reservations_after"] == 0
report = {
    "schema": "pharma.local-observability-acceptance.v1",
    "schema_version": 1,
    "status": "passed",
    "generated_at": datetime.now(UTC).isoformat(),
    "environment": "local-wsl",
    "production_claim": False,
    "collector_protocol": "OTLP-gRPC",
    "observed_metrics": os.environ["OBSERVED_METRICS"].split(","),
    "contract": {
        "services": contract["service_count"],
        "objectives": contract["objective_count"],
        "alerts": contract["alert_count"],
    },
    "commercial_probe": {
        "requests": load["requests"]["completed"],
        "unique_settlements": load["billing"]["unique_settlement_ids"],
        "active_reservations_after": load["billing"]["active_reservations_after"],
        "p95_ms": load["latency_ms"]["p95"],
    },
    "credentials_recorded": False,
}
Path(sys.argv[3]).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

cat "$work/report.json"
if [[ -n "$output_path" ]]; then
  output_parent=$(dirname -- "$output_path")
  output_name=$(basename -- "$output_path")
  [[ "$output_name" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]] || { echo "invalid output filename" >&2; exit 2; }
  mkdir -p "$output_parent"
  output_parent=$(realpath "$output_parent")
  output_path="$output_parent/$output_name"
  [[ ! -e "$output_path" && ! -L "$output_path" ]] || { echo "refusing to overwrite output" >&2; exit 1; }
  temporary="$output_path.partial.$$"
  cp "$work/report.json" "$temporary"
  chmod 600 "$temporary"
  mv -- "$temporary" "$output_path"
fi
