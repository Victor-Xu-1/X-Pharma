#!/usr/bin/env bash

runtime_archive_image() {
  printf '%s\n' 'busybox:1.36.1@sha256:73aaf090f3d85aa34ee199857f03fa3a95c8ede2ffd4cc2cdb5b94e566b11662'
}

# One owner for short-lived archive containers; stdout remains the archive stream.
run_runtime_archive() (
  set -Eeuo pipefail
  umask 077
  # EXIT may run after an errexit unwinds function locals. This subshell already
  # isolates state from callers; keep trap-owned identity alive until cleanup ends.
  name=${1:-}
  image="" container_id="" parent="" work="" owner=""
  mounts=()
  [[ "$name" =~ ^pharma-(backup|restore)-archive-[1-9][0-9]*-[1-9][0-9]*-(object|markdown)-(write|list|extract|probe)$ ]] || {
    echo 'Refusing an unexpected archive container name' >&2; return 2;
  }
  shift
  while [[ ${1:-} == --mount ]]; do
    [[ $# -ge 2 ]] || return 2
    mounts+=(--mount "$2")
    shift 2
  done
  [[ ${1:-} == -- && ${2:-} == tar ]] || return 2
  shift
  image=$(runtime_archive_image)
  parent=$(realpath -e -- "${TMPDIR:-/tmp}")
  [[ "$parent" != / && -d "$parent" ]] || return 2
  work=$(mktemp -d "$parent/pharma-archive.XXXXXX")
  owner=$(basename -- "$work")

  cleanup_archive() {
    local owned remaining actual_name actual_id
    owned=$(timeout --kill-after=2s 5s docker container ls -a --no-trunc --filter "label=io.pharma.archive-owner=$owner" --filter "name=^/$name$" --format '{{.ID}} {{.Names}}') || return 1
    if [[ -n "$owned" ]]; then
      [[ "$owned" =~ ^[a-f0-9]{64}\ [a-z0-9-]+$ ]] || return 1
      read -r actual_id actual_name <<< "$owned"
      [[ "$actual_name" == "$name" ]] || return 1
      timeout --kill-after=2s 15s docker rm -f "$actual_id" >/dev/null 2>&1 || true
    fi
    remaining=$(timeout --kill-after=2s 5s docker container ls -a --no-trunc --filter "label=io.pharma.archive-owner=$owner" --filter "name=^/$name$" --format '{{.ID}} {{.Names}}') || return 1
    [[ -z "$remaining" ]] || return 1
    [[ ! -L "$work" && -d "$work" && "$(realpath -e -- "$work")" == "$work" \
      && "$(dirname -- "$work")" == "$parent" && "$owner" =~ ^pharma-archive\.[A-Za-z0-9]{6}$ ]] || return 1
    rm -rf -- "$work"
  }
  finish_archive() {
    local result=$?
    trap - EXIT INT TERM
    if ! cleanup_archive; then
      printf 'Archive cleanup is incomplete; retained workspace=%s container=%s\n' "$work" "$name" >&2
      [[ $result -ne 0 ]] || result=1
    fi
    exit "$result"
  }
  trap finish_archive EXIT
  trap 'exit 130' INT
  trap 'exit 143' TERM

  container_id=$(timeout --kill-after=2s 20s docker create --pull=never --network none --read-only --interactive --name "$name" \
    --label "io.pharma.archive-owner=$owner" "${mounts[@]}" "$image" "$@")
  [[ "$container_id" =~ ^[a-f0-9]{64}$ ]] || return 1
  timeout --kill-after=2s 120s docker start --attach --interactive "$container_id"
  [[ $(timeout --kill-after=2s 5s docker inspect --format '{{.State.Status}} {{.State.ExitCode}}' "$container_id") == 'exited 0' ]] || {
    echo 'Archive container did not exit successfully' >&2; return 1;
  }
)
