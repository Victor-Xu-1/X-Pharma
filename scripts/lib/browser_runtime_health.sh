#!/usr/bin/env bash

wait_for_browser_container_healthy() {
  local container_id=${1:?Expected task-owned container id}
  local service=${2:?Expected service label}
  local budget=${3:?Expected positive wait budget}
  [[ "$budget" =~ ^[1-9][0-9]*$ && "$budget" -le 60 ]] || return 2
  local deadline=$((SECONDS + budget))
  local state=unknown
  local remaining inspect_budget
  while ((SECONDS < deadline)); do
    remaining=$((deadline - SECONDS))
    inspect_budget=$((remaining < 5 ? remaining : 5))
    state=$(timeout --signal=TERM --kill-after=1s "${inspect_budget}s" docker inspect \
      --format '{{.State.Running}} {{if .State.Health}}{{.State.Health.Status}}{{else}}missing{{end}}' \
      "$container_id" 2>/dev/null) || state=unknown
    if [[ "$state" == 'true healthy' ]]; then
      return 0
    fi
    if [[ "$state" == false\ * || "$state" == 'true missing' ]]; then
      break
    fi
    sleep 1
  done
  printf 'Browser acceptance %s did not become healthy within %ss: %s\n' "$service" "$budget" "$state" >&2
  return 1
}
