#!/usr/bin/env bash
set -Eeuo pipefail

umask 077

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$root"
output_path=""
backup_root="$root/backups/release-candidates"
project_name="${COMPOSE_PROJECT_NAME:-pharma-intelligence}"
quiesce_runtime=0
started_epoch=$(date +%s)

usage() {
  cat <<'EOF'
Usage: verify-local-backup-restore.sh [--output FILE] [--backup-root DIR]
       [--project-name NAME] [--quiesce-runtime]

Create a checksummed local WSL authority backup and restore it into isolated
containers and volumes. The successful backup is retained below backups/;
database dumps and archives are never copied into release evidence.

--quiesce-runtime briefly pauses application writers and Temporal while the
authority snapshot is captured, then always resumes containers before restore
verification. Use it for a deterministic release gate on an active runtime.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --output)
      [[ $# -ge 2 ]] || { echo "--output requires a value" >&2; exit 2; }
      output_path=$2
      shift 2
      ;;
    --backup-root)
      [[ $# -ge 2 ]] || { echo "--backup-root requires a value" >&2; exit 2; }
      backup_root=$2
      shift 2
      ;;
    --project-name)
      [[ $# -ge 2 ]] || { echo "--project-name requires a value" >&2; exit 2; }
      project_name=$2
      shift 2
      ;;
    --quiesce-runtime)
      quiesce_runtime=1
      shift
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

[[ "$project_name" =~ ^[a-z0-9][a-z0-9_-]*$ ]] || {
  echo "unsafe Compose project name: $project_name" >&2
  exit 2
}
for command in docker python3 realpath dirname basename mktemp sha256sum; do
  command -v "$command" >/dev/null 2>&1 || {
    echo "required command is unavailable: $command" >&2
    exit 1
  }
done
mkdir -p "$backup_root"
backup_root=$(realpath "$backup_root")
authority_root=$(realpath "$root/backups")
case "$backup_root/" in
  "$authority_root"/*) ;;
  *) echo "backup root must remain below $authority_root" >&2; exit 2 ;;
esac
chmod 700 "$backup_root"

work=$(mktemp -d -t pharma-backup-restore-acceptance.XXXXXX)
paused_containers=()
watchdog_unit=""

resume_runtime_writers() {
  local failed=0 index container
  for (( index=${#paused_containers[@]}-1; index>=0; index-- )); do
    container=${paused_containers[$index]}
    if [[ $(docker inspect --format '{{.State.Paused}}' "$container" 2>/dev/null || true) == true ]]; then
      docker unpause "$container" >/dev/null || failed=1
    fi
  done
  if [[ $failed -ne 0 ]]; then
    return 1
  fi
  paused_containers=()
  if [[ -n "$watchdog_unit" ]]; then
    systemctl --user stop "$watchdog_unit.timer" >/dev/null 2>&1 || true
    systemctl --user reset-failed "$watchdog_unit.service" "$watchdog_unit.timer" >/dev/null 2>&1 || true
    watchdog_unit=""
  fi
}

cleanup() {
  resume_runtime_writers || echo "failed to resume one or more quiesced runtime containers" >&2
  case "$work" in
    /tmp/pharma-backup-restore-acceptance.*) rm -rf -- "$work" ;;
    *) echo "refusing to clean unexpected backup acceptance workspace: $work" >&2 ;;
  esac
}
trap cleanup EXIT INT TERM

if [[ $quiesce_runtime -eq 1 ]]; then
  for command in systemctl systemd-run; do
    command -v "$command" >/dev/null 2>&1 || {
      echo "required quiesce recovery command is unavailable: $command" >&2
      exit 1
    }
  done
  compose=(
    docker compose
    --project-name "$project_name"
    -f compose.yaml
    -f compose.dev.yaml
    -f compose.telemetry.yaml
  )
  writer_services=(api worker temporal)
  writer_containers=()
  for service in "${writer_services[@]}"; do
    container=$("${compose[@]}" ps -q "$service")
    [[ -n "$container" ]] || {
      echo "required runtime writer service is unavailable: $service" >&2
      exit 1
    }
    state=$(docker inspect --format '{{.State.Running}} {{.State.Paused}}' "$container")
    [[ "$state" == "true false" ]] || {
      echo "runtime writer service is not running and unpaused: $service ($state)" >&2
      exit 1
    }
    [[ "$container" =~ ^[a-f0-9]{12,64}$ ]] || {
      echo "runtime writer service returned an unsafe container id: $service" >&2
      exit 1
    }
    writer_containers+=("$container")
  done
  watchdog_unit="pharma-backup-resume-$$-$(date +%s)"
  systemd-run --user --quiet --unit="$watchdog_unit" --on-active=10m \
    "$(command -v docker)" unpause "${writer_containers[@]}"
  systemctl --user is-active --quiet "$watchdog_unit.timer" || {
    echo "failed to arm the independent runtime resume watchdog" >&2
    exit 1
  }
  paused_containers=("${writer_containers[@]}")
  docker pause "${paused_containers[@]}" >/dev/null
fi

backup_path=$(./scripts/backup-runtime-linux.sh --output-root "$backup_root" --project-name "$project_name")
backup_path=$(realpath "$backup_path")
case "$backup_path/" in
  "$backup_root"/*) ;;
  *) echo "backup command returned a path outside the requested root" >&2; exit 1 ;;
esac
resume_runtime_writers || {
  echo "failed to resume the quiesced runtime after backup capture" >&2
  exit 1
}
./scripts/restore-smoke-linux.sh "$backup_path" > "$work/restore.json"
chmod 600 "$work/restore.json"

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
python3 - "$backup_path/manifest.json" "$backup_path/checksums.sha256" "$work/restore.json" \
  "$backup_path" "$authority_root" "$duration_seconds" "$output_path" <<'PY'
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

manifest_path, checksums_path, restore_path, backup_text, authority_text, duration, output_text = sys.argv[1:]
manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
restore = json.loads(Path(restore_path).read_text(encoding="utf-8"))
backup = Path(backup_text).resolve()
authority = Path(authority_text).resolve()
try:
    backup_relative = backup.relative_to(authority)
except ValueError as exc:
    raise SystemExit("backup path escaped the configured backup authority root") from exc
backup_reference = (Path("backups") / backup_relative).as_posix()
if restore.get("status") != "passed" or restore.get("main_runtime_modified") is not False:
    raise SystemExit("isolated restore smoke did not pass without modifying the main runtime")
if restore.get("rls_probe") != "passed" or restore.get("temporal_databases_restored") != 2:
    raise SystemExit("restored RLS or Temporal authority verification failed")
if not isinstance(restore.get("tables_verified"), int) or restore["tables_verified"] < 1:
    raise SystemExit("restored application table inventory is empty")
if restore.get("archives_verified") != 2:
    raise SystemExit("restored object and Markdown archives were not both verified")
if not isinstance(restore.get("alembic_head"), str) or not restore["alembic_head"]:
    raise SystemExit("restored Alembic head is missing")
if not isinstance(restore.get("rdkit_version"), str) or not restore["rdkit_version"]:
    raise SystemExit("restored RDKit extension version is missing")
authority = manifest.get("authority")
artifacts = manifest.get("artifacts")
if not isinstance(authority, list) or len(authority) < 6 or not isinstance(artifacts, dict):
    raise SystemExit("backup authority manifest is incomplete")
for name in authority:
    metadata = artifacts.get(name)
    if not isinstance(metadata, dict) or not isinstance(metadata.get("sizeBytes"), int) or metadata["sizeBytes"] < 1:
        raise SystemExit(f"backup artifact metadata is invalid: {name}")
def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
report = {
    "schema": "pharma.local-backup-restore-acceptance.v1",
    "schema_version": 1,
    "generated_at": restore.get("created_at"),
    "status": "passed",
    "environment": "local-wsl",
    "production_claim": False,
    "credentials_recorded": False,
    "backup_reference": backup_reference,
    "backup_manifest_sha256": digest(Path(manifest_path)),
    "backup_checksums_sha256": digest(Path(checksums_path)),
    "authority_artifacts": len(authority),
    "authority_bytes": sum(artifacts[name]["sizeBytes"] for name in authority),
    "tables_verified": restore.get("tables_verified"),
    "alembic_head": restore.get("alembic_head"),
    "rdkit_version": restore.get("rdkit_version"),
    "temporal_databases_restored": restore.get("temporal_databases_restored"),
    "rls_probe": restore.get("rls_probe"),
    "archives_verified": restore.get("archives_verified"),
    "main_runtime_modified": False,
    "duration_seconds": int(duration),
    "sensitive_backup_embedded": False,
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
            raise SystemExit(f"refusing to overwrite backup/restore evidence: {output}") from exc
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
  printf 'backup_restore_report=%s\n' "$output_path"
fi
