#!/usr/bin/env bash
set -Eeuo pipefail

umask 077

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
source_id=""
ingestion_output=""
automatic_output=""
automatic_timeout=900
project_name="${COMPOSE_PROJECT_NAME:-pharma-intelligence}"

usage() {
  cat <<'EOF'
Usage: verify-pilot-ingestion.sh --source-id UUID --ingestion-output FILE --automatic-output FILE [options]

Capture unattended Temporal ingestion first, then governed idempotence evidence
for the same registered real source. The acceptance never pre-consumes source
objects with a manual scan before observing the scheduler.

Options:
  --automatic-timeout-seconds N  Scheduler observation limit (default: 900).
  --project-name NAME            Compose project owning the runtime (default: COMPOSE_PROJECT_NAME or pharma-intelligence).
  -h, --help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --source-id)
      [[ $# -ge 2 ]] || { echo "--source-id requires a value" >&2; exit 2; }
      source_id=$2
      shift 2
      ;;
    --ingestion-output)
      [[ $# -ge 2 ]] || { echo "--ingestion-output requires a value" >&2; exit 2; }
      ingestion_output=$2
      shift 2
      ;;
    --automatic-output)
      [[ $# -ge 2 ]] || { echo "--automatic-output requires a value" >&2; exit 2; }
      automatic_output=$2
      shift 2
      ;;
    --automatic-timeout-seconds)
      [[ $# -ge 2 ]] || { echo "--automatic-timeout-seconds requires a value" >&2; exit 2; }
      automatic_timeout=$2
      shift 2
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

[[ "$source_id" =~ ^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$ ]] || {
  echo "--source-id must be a UUID" >&2
  exit 2
}
[[ -n "$ingestion_output" && -n "$automatic_output" && "$ingestion_output" != "$automatic_output" ]] || {
  echo "two distinct ingestion evidence paths are required" >&2
  exit 2
}
[[ "$automatic_timeout" =~ ^[1-9][0-9]*$ && "$automatic_timeout" -ge 60 && "$automatic_timeout" -le 86400 ]] || {
  echo "--automatic-timeout-seconds must be between 60 and 86400" >&2
  exit 2
}
[[ "$project_name" =~ ^[a-z0-9][a-z0-9_-]*$ ]] || {
  echo "--project-name must contain only lowercase letters, digits, underscores or hyphens" >&2
  exit 2
}

"$root/scripts/verify-automatic-ingestion.sh" \
  --source-id "$source_id" \
  --timeout-seconds "$automatic_timeout" \
  --project-name "$project_name" \
  --output "$automatic_output"
"$root/scripts/verify-local-ingestion.sh" \
  --source-id "$source_id" \
  --project-name "$project_name" \
  --output "$ingestion_output"
