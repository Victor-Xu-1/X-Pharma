#!/usr/bin/env bash
set -Eeuo pipefail

umask 077

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$root"
source "$root/scripts/lib/runtime_archive_container.sh"
source "$root/scripts/lib/runtime_backup_lifecycle.sh"
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
authority snapshot is captured. Confirmed writer recovery precedes restore
verification; failed or unknown recovery is never accepted as a passed gate.

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
for command in docker python3 realpath dirname basename mktemp sha256sum timeout stat rmdir flock; do
  command -v "$command" >/dev/null 2>&1 || {
    echo "required command is unavailable: $command" >&2
    exit 1
  }
done
if [[ -n "$postgres_image_id" ]]; then
  if ! inspected_postgres_image=$(runtime_backup_docker 5 image inspect "$postgres_image_id" --format '{{.Id}}'); then
    echo "target PostgreSQL image inspection failed" >&2
    exit 1
  fi
  [[ "$inspected_postgres_image" == "$postgres_image_id" ]] || {
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

runtime_backup_lifecycle_init "$authority_root"
if [[ $quiesce_runtime -eq 1 ]]; then
  runtime_backup_quiesce "$project_name"
fi

backup_path=$(./scripts/backup-runtime-linux.sh --output-root "$backup_root" --project-name "$project_name")
backup_path=$(realpath "$backup_path")
case "$backup_path/" in
  "$backup_root"/*) ;;
  *) echo "backup command returned a path outside the requested root" >&2; exit 1 ;;
esac
runtime_backup_resume || {
  echo "failed to resume the quiesced runtime after backup capture" >&2
  exit 1
}
restore_arguments=("$backup_path")
if [[ -n "$postgres_image_id" ]]; then
  restore_arguments+=(--postgres-image-id "$postgres_image_id")
fi
./scripts/restore-smoke-linux.sh "${restore_arguments[@]}" > "$backup_lifecycle_work/restore.json"
chmod 600 "$backup_lifecycle_work/restore.json"

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
restore_result=$(< "$backup_lifecycle_work/restore.json")
runtime_backup_lifecycle_cleanup || {
  echo "Fresh-backup recovery/cleanup is incomplete; no passed report will be published" >&2
  exit 1
}
duration_seconds=$(( $(date +%s) - started_epoch ))
printf '%s\n' "$restore_result" | python3 "$root/scripts/lib/runtime_backup_report.py" \
  "$backup_path/manifest.json" "$backup_path/checksums.sha256" /dev/stdin \
  "$backup_path" "$authority_root" "$duration_seconds" "$output_path" "$postgres_image_id"

if [[ -n "$output_path" ]]; then
  printf 'backup_restore_report=%s\n' "$output_path"
fi
