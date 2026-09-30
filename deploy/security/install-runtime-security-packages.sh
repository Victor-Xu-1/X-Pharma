#!/usr/bin/env bash
set -Eeuo pipefail

lock=${1:?Pass the reviewed Debian security package lock}
[[ -f "$lock" && ! -L "$lock" ]] || { echo "Security package lock is not a regular file" >&2; exit 1; }
packages=()
while IFS= read -r line || [[ -n "$line" ]]; do
  [[ -z "$line" || "$line" == \#* ]] && continue
  [[ "$line" =~ ^([a-z0-9][a-z0-9+.-]*)=([a-zA-Z0-9:+.~_-]+)$ ]] || {
    echo "Invalid security package lock entry" >&2
    exit 1
  }
  package=${BASH_REMATCH[1]}
  version=${BASH_REMATCH[2]}
  status=$(dpkg-query -W -f='${Status}' "$package" 2>/dev/null || true)
  [[ "$status" == "install ok installed" ]] || continue
  installed=$(dpkg-query -W -f='${Version}' "$package")
  if dpkg --compare-versions "$installed" gt "$version"; then
    echo "Review the lock before downgrading a newer security package: $package" >&2
    exit 1
  fi
  packages+=("$package=$version")
done < "$lock"
[[ ${#packages[@]} -gt 0 ]] || { echo "No installed packages matched the reviewed security lock" >&2; exit 1; }

timeout --foreground --signal=TERM --kill-after=15s 600s apt-get \
  -o Acquire::Retries=3 -o Acquire::http::Timeout=30 -o Acquire::https::Timeout=30 update
DEBIAN_FRONTEND=noninteractive timeout --foreground --signal=TERM --kill-after=15s 600s apt-get \
  -o Acquire::Retries=3 -o Acquire::http::Timeout=30 -o Acquire::https::Timeout=30 \
  install --yes --no-install-recommends "${packages[@]}"
