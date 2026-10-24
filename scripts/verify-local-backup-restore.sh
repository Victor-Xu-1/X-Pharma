#!/usr/bin/env bash
set -Eeuo pipefail

umask 077

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$root"
source "$root/scripts/lib/runtime_archive_container.sh"
output_path=""
backup_root="$root/backups/release-candidates"
project_name="${COMPOSE_PROJECT_NAME:-pharma-intelligence}"
quiesce_runtime=0
postgres_image_id=""
started_epoch=$(date +%s)

usage() {
  cat <<'EOF'
Usage: verify-local-backup-restore.sh [--output FILE] [--backup-root DIR]
       [--project-name NAME] [--quiesce-runtime] [--postgres-image-id sha256:IMAGE_ID]

Create a checksummed local WSL authority backup and restore it into isolated
containers and volumes. The successful backup is retained below backups/;
database dumps and archives are never copied into release evidence.

--quiesce-runtime briefly pauses application writers and Temporal while the
authority snapshot is captured, then always resumes containers before restore
verification. Use it for a deterministic release gate on an active runtime.

--postgres-image-id tests an installed immutable target image in the isolated
restore only. It never pulls an image, changes the backup, or deploys the target.
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
    --postgres-image-id)
      [[ $# -ge 2 && -z "$postgres_image_id" ]] || { echo "--postgres-image-id requires one value" >&2; exit 2; }
      [[ "$2" =~ ^sha256:[a-f0-9]{64}$ ]] || {
        echo "--postgres-image-id requires an immutable lowercase sha256 image ID" >&2
        exit 2
      }
      postgres_image_id=$2
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
if [[ -n "$postgres_image_id" ]]; then
  [[ $(docker image inspect "$postgres_image_id" --format '{{.Id}}') == "$postgres_image_id" ]] || {
    echo "target PostgreSQL image is unavailable or its identity differs" >&2
    exit 1
  }
fi
# Prove archive execution and removal before arming a watchdog or pausing writers.
run_runtime_archive "pharma-backup-archive-$started_epoch-$$-object-probe" \
  -- tar -cf - -T /dev/null >/dev/null

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
restore_arguments=("$backup_path")
if [[ -n "$postgres_image_id" ]]; then
  restore_arguments+=(--postgres-image-id "$postgres_image_id")
fi
./scripts/restore-smoke-linux.sh "${restore_arguments[@]}" > "$work/restore.json"
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
python3 "$root/scripts/lib/runtime_backup_report.py" \
  "$backup_path/manifest.json" "$backup_path/checksums.sha256" "$work/restore.json" \
  "$backup_path" "$authority_root" "$duration_seconds" "$output_path" "$postgres_image_id"

if [[ -n "$output_path" ]]; then
  printf 'backup_restore_report=%s\n' "$output_path"
fi
