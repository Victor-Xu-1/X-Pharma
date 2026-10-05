#!/usr/bin/env bash

# Keep masked fixture labels geometrically stable without reducing nonce entropy.
browser_fixture_run_id() {
  local stamp=${1:?Expected a UTC timestamp}
  local nonce=${2:?Expected a Bash RANDOM nonce}
  [[ "$stamp" =~ ^[0-9]{14}$ && "$nonce" =~ ^[0-9]{1,5}$ ]] || return 2
  ((10#$nonce <= 32767)) || return 2
  printf '%s-%05d\n' "$stamp" "$((10#$nonce))"
}
