#!/usr/bin/env bash

entry_staging_remove() {
  local expected_parent=${1:?Expected entry staging parent}
  local target=${2:?Expected owned entry fixture directory}
  local resolved_parent resolved_target
  resolved_parent=$(realpath -e -- "$expected_parent") || return 1
  resolved_target=$(realpath -e -- "$target") || return 1
  if [[ "$resolved_parent" == / || -L "$target" || ! -d "$target" \
      || "$resolved_target" != "$target" \
      || "$(dirname -- "$resolved_target")" != "$resolved_parent" \
      || "$(basename -- "$resolved_target")" != pharma-entry-consistency.* ]]; then
    printf 'Refusing an entry fixture outside the verified parent\n' >&2
    return 1
  fi
  # Only our flat receipt/cookie files are expected. Reject nested directories
  # or symlinks rather than traversing an unexpected tree.
  if [[ -n "$(find "$resolved_target" -mindepth 1 ! -type f -print -quit)" ]]; then
    printf 'Refusing unexpected entry fixture contents\n' >&2
    return 1
  fi
  find "$resolved_target" -mindepth 1 -maxdepth 1 -type f -delete || return 1
  rmdir -- "$resolved_target"
}
