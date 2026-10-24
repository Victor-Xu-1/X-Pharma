#!/usr/bin/env bash

# This owner never starts/replaces a business container or recursively removes a directory.
runtime_backup_docker() {
  local seconds=${1:-}
  [[ "$seconds" =~ ^[1-9][0-9]*$ && ${#seconds} -le 2 && "$seconds" -le 30 ]] || return 2
  shift
  timeout --kill-after=2s "${seconds}s" docker "$@"
}

runtime_backup_lifecycle_init() {
  [[ $# -eq 1 ]] || return 2
  local authority
  authority=$(realpath -e -- "$1") || return 2
  [[ "$authority" != / && -d "$authority" ]] || return 2
  # Lock the existing authority directory, not a removable/replaceable lock file.
  exec {backup_lifecycle_lock_fd}< "$authority"
  flock -n "$backup_lifecycle_lock_fd" || {
    echo 'Another fresh-backup acceptance owns this authority directory' >&2; return 1;
  }
  backup_lifecycle_parent=$(realpath -e -- "${TMPDIR:-/tmp}") || return 2
  [[ "$backup_lifecycle_parent" != / && -d "$backup_lifecycle_parent" ]] || return 2
  backup_lifecycle_work="" backup_lifecycle_identity="" backup_lifecycle_watchdog=""
  backup_lifecycle_ids=() backup_lifecycle_services=(api worker temporal)
  backup_lifecycle_pending=0 backup_lifecycle_cleaned=0 backup_lifecycle_project=""
  trap runtime_backup_lifecycle_finish EXIT
  trap 'exit 130' INT
  trap 'exit 143' TERM
  backup_lifecycle_work=$(mktemp -d "$backup_lifecycle_parent/pharma-backup-restore-acceptance.XXXXXX") || return 1
  backup_lifecycle_identity=$(stat -c '%d:%i' -- "$backup_lifecycle_work") || return 1
}

runtime_backup_writer_state() {
  local index=$1 identity id=${backup_lifecycle_ids[$1]}
  identity=$(runtime_backup_docker 5 inspect --format \
    '{{.Id}} {{index .Config.Labels "com.docker.compose.project"}} {{index .Config.Labels "com.docker.compose.service"}} {{.State.Running}} {{.State.Paused}}' "$id") || return 1
  case "$identity" in
    "$id $backup_lifecycle_project ${backup_lifecycle_services[$index]} true true") printf 'true\n' ;;
    "$id $backup_lifecycle_project ${backup_lifecycle_services[$index]} true false") printf 'false\n' ;;
    *) echo "Writer identity/state changed: $id" >&2; return 1 ;;
  esac
}

runtime_backup_quiesce() {
  local project=${1:-} index service id state
  [[ "$project" =~ ^[a-z0-9][a-z0-9_-]*$ && ${#backup_lifecycle_ids[@]} -eq 0 ]] || return 2
  for command in systemctl systemd-run; do command -v "$command" >/dev/null || return 127; done
  backup_lifecycle_project=$project
  for service in "${backup_lifecycle_services[@]}"; do
    id=$(runtime_backup_docker 10 compose --project-name "$project" \
      -f compose.yaml -f compose.dev.yaml -f compose.telemetry.yaml ps -q "$service") || return 1
    [[ "$id" =~ ^[a-f0-9]{64}$ ]] || return 1
    for state in "${backup_lifecycle_ids[@]}"; do [[ "$state" != "$id" ]] || return 1; done
    backup_lifecycle_ids+=("$id")
    index=$(( ${#backup_lifecycle_ids[@]} - 1 ))
    state=$(runtime_backup_writer_state "$index") || return 1
    [[ "$state" == false ]] || { echo "Writer already paused: $service" >&2; return 1; }
  done
  printf '%s\n' "${backup_lifecycle_ids[@]}" > "$backup_lifecycle_work/writers.txt"
  backup_lifecycle_watchdog="pharma-backup-resume-$$-$(date +%s)"
  timeout --kill-after=2s 10s systemd-run --user --quiet --unit="$backup_lifecycle_watchdog" --on-active=10m \
    "$(command -v timeout)" --kill-after=2s 30s "$(command -v docker)" unpause "${backup_lifecycle_ids[@]}" || return 1
  timeout --kill-after=2s 10s systemctl --user is-active --quiet "$backup_lifecycle_watchdog.timer" || return 1
  # Record the entire attempted set before pause: a failed/lost reply may have paused a subset.
  backup_lifecycle_pending=1
  runtime_backup_docker 15 pause "${backup_lifecycle_ids[@]}" >/dev/null || return 1
  for index in "${!backup_lifecycle_ids[@]}"; do
    state=$(runtime_backup_writer_state "$index") || return 1
    [[ "$state" == true ]] || return 1
  done
}

runtime_backup_resume() {
  local index state failed=0 timer_state timer_status
  if [[ "$backup_lifecycle_pending" == 1 ]]; then
    for (( index=${#backup_lifecycle_ids[@]}-1; index>=0; index-- )); do
      if ! state=$(runtime_backup_writer_state "$index"); then failed=1; continue; fi
      if [[ "$state" == true ]]; then
        if ! runtime_backup_docker 15 unpause "${backup_lifecycle_ids[$index]}" >/dev/null; then
          failed=1; continue
        fi
      fi
      if ! state=$(runtime_backup_writer_state "$index") || [[ "$state" != false ]]; then failed=1; fi
    done
    # Unknown state cannot imply success or cancel the independent recovery watchdog.
    [[ "$failed" == 0 ]] || return 1
  fi
  if [[ -n "$backup_lifecycle_watchdog" ]]; then
    timeout --kill-after=2s 10s systemctl --user stop "$backup_lifecycle_watchdog.timer" || return 1
    timer_status=0
    timer_state=$(timeout --kill-after=2s 10s systemctl --user is-active "$backup_lifecycle_watchdog.timer") || timer_status=$?
    [[ "$timer_status" == 3 && "$timer_state" == inactive ]] || return 1
    backup_lifecycle_watchdog=""
  fi
  backup_lifecycle_pending=0
}

runtime_backup_workspace_is_owned() {
  [[ -n "$backup_lifecycle_identity" && ! -L "$backup_lifecycle_work" && -d "$backup_lifecycle_work" \
    && "$(realpath -e -- "$backup_lifecycle_parent")" == "$backup_lifecycle_parent" \
    && "$(realpath -e -- "$backup_lifecycle_work")" == "$backup_lifecycle_work" \
    && "$(dirname -- "$backup_lifecycle_work")" == "$backup_lifecycle_parent" \
    && "$(basename -- "$backup_lifecycle_work")" =~ ^pharma-backup-restore-acceptance\.[A-Za-z0-9]{6}$ \
    && "$(stat -c '%d:%i' -- "$backup_lifecycle_work")" == "$backup_lifecycle_identity" ]] || {
    echo 'Refusing an unowned fresh-backup workspace' >&2; return 1;
  }
}

runtime_backup_lifecycle_cleanup() {
  local path name
  [[ "$backup_lifecycle_cleaned" != 1 ]] || return 0
  runtime_backup_resume || return 1
  runtime_backup_workspace_is_owned || return 1
  # Inspect every entry before deleting anything; retain unknown data and symlinks.
  for path in "$backup_lifecycle_work"/* "$backup_lifecycle_work"/.[!.]* "$backup_lifecycle_work"/..?*; do
    [[ -e "$path" || -L "$path" ]] || continue
    name=$(basename -- "$path")
    [[ ( "$name" == restore.json || "$name" == writers.txt ) && -f "$path" && ! -L "$path" ]] || {
      echo "Unexpected fresh-backup workspace entry: $name" >&2; return 1;
    }
  done
  for name in restore.json writers.txt; do
    path="$backup_lifecycle_work/$name"
    if [[ -e "$path" ]]; then rm -- "$path" || return 1; fi
  done
  rmdir -- "$backup_lifecycle_work" || return 1
  backup_lifecycle_cleaned=1
}

runtime_backup_lifecycle_finish() {
  local result=$?
  trap - EXIT INT TERM
  if [[ -n "$backup_lifecycle_work" ]] && ! runtime_backup_lifecycle_cleanup; then
    printf 'Fresh-backup cleanup/recovery unconfirmed; retained workspace=%s watchdog=%s\n' \
      "$backup_lifecycle_work" "$backup_lifecycle_watchdog" >&2
    [[ "$result" != 0 ]] || result=1
  fi
  exit "$result"
}
