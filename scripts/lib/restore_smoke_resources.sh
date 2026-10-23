#!/usr/bin/env bash

# One cleanup owner; never infer an online project, volume or arbitrary directory.
restore_smoke_cleanup() {
  [[ $# -eq 7 ]] || { echo 'Invalid isolated restore cleanup arguments' >&2; return 2; }
  local expected_parent=$1 workspace=$2 postgres=$3 probe=$4
  shift 4
  local volumes=("$@") suffix resolved_parent resolved_workspace remaining name volume
  [[ "$postgres" =~ ^pharma-restore-smoke-([1-9][0-9]*-[1-9][0-9]*)$ ]] || {
    echo 'Refusing an unexpected restore container identity' >&2; return 2;
  }
  suffix=${postgres#pharma-restore-smoke-}
  [[ "$probe" == "$postgres-rls" && "${volumes[0]}" == "pharma-restore-smoke-postgres-$suffix" \
    && "${volumes[1]}" == "pharma-restore-smoke-object-$suffix" \
    && "${volumes[2]}" == "pharma-restore-smoke-markdown-$suffix" ]] || {
    echo 'Refusing restore resources outside the exact isolated run' >&2; return 2;
  }
  resolved_parent=$(realpath -e -- "$expected_parent") || return 2
  resolved_workspace=$(realpath -e -- "$workspace") || return 2
  [[ "$resolved_parent" != / && "$resolved_parent" == "$expected_parent" \
    && ! -L "$workspace" && -d "$workspace" && "$resolved_workspace" == "$workspace" \
    && "$(dirname -- "$resolved_workspace")" == "$resolved_parent" \
    && "$(basename -- "$resolved_workspace")" =~ ^pharma-restore-smoke\.[A-Za-z0-9]{6}$ ]] || {
    echo 'Refusing an unexpected restore work directory' >&2; return 2;
  }

  # Missing resources are harmless; an unavailable daemon or a retained resource is not.
  timeout --kill-after=2s 15s docker rm -f "$probe" "$postgres" >/dev/null 2>&1 || true
  if ! remaining=$(timeout --kill-after=2s 5s docker container ls -a --format '{{.Names}}'); then
    echo 'Cannot verify isolated restore container removal' >&2; return 1
  fi
  while IFS= read -r name; do
    if [[ "$name" == "$postgres" || "$name" == "$probe" ]]; then
      echo "Isolated restore container is still present: $name" >&2; return 1
    fi
  done <<< "$remaining"

  timeout --kill-after=2s 10s docker volume rm "${volumes[@]}" >/dev/null 2>&1 || true
  if ! remaining=$(timeout --kill-after=2s 5s docker volume ls --format '{{.Name}}'); then
    echo 'Cannot verify isolated restore volume removal' >&2; return 1
  fi
  while IFS= read -r name; do
    for volume in "${volumes[@]}"; do
      if [[ "$name" == "$volume" ]]; then
        echo "Isolated restore volume is still present: $name" >&2; return 1
      fi
    done
  done <<< "$remaining"
  rm -rf -- "$resolved_workspace"
}
