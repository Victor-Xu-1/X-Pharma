#!/usr/bin/env bash

security_staging_remove() {
  local expected_parent=${1:?Expected staging parent}
  local target=${2:?Expected task-owned staging directory}
  local resolved_parent resolved_target
  resolved_parent=$(realpath -e -- "$expected_parent") || return 1
  resolved_target=$(realpath -e -- "$target") || return 1
  if [[ "$resolved_parent" == / || -L "$target" || ! -d "$target" \
      || "$resolved_target" != "$target" \
      || "$(dirname -- "$resolved_target")" != "$resolved_parent" \
      || "$(basename -- "$resolved_target")" != pharma-security.* ]]; then
    printf 'Refusing to remove an unexpected security staging directory: %s\n' "$target" >&2
    return 1
  fi
  chmod -R u+w -- "$resolved_target" || return 1
  rm -rf -- "$resolved_target"
}
