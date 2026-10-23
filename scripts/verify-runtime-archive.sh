#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
source "$root/scripts/lib/runtime_archive_container.sh"
if [[ $# -eq 1 && $1 == --help ]]; then
  printf 'Verify a fixture-only archive round trip with the installed pinned image; never pulls or reads runtime volumes.\n'
  exit 0
fi
[[ $# -eq 0 ]] || exit 2
for command in docker timeout realpath mktemp git cmp python3; do
  command -v "$command" >/dev/null || exit 1
done
image=$(runtime_archive_image)
timeout --kill-after=2s 5s docker image inspect "$image" >/dev/null
revision=$(git -C "$root" rev-parse HEAD)
[[ "$revision" =~ ^[a-f0-9]{40}$ ]] || exit 1
parent=$(realpath -e -- "${TMPDIR:-/tmp}")
[[ "$parent" != / && -d "$parent" ]] || exit 2
work=$(mktemp -d "$parent/pharma-archive-contract.XXXXXX")
complete=0
finish() {
  result=$?
  trap - EXIT INT TERM
  if [[ $complete -ne 1 ]]; then
    [[ $result -ne 0 ]] || result=1
    printf 'Archive probe failed; retained fixture=%s\n' "$work" >&2
  fi
  exit "$result"
}
trap finish EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

mkdir "$work/input" "$work/output"
printf 'X-Pharma archive fixture\000\377\n' > "$work/input/probe.bin"
suffix="$(date +%s)-$$"
run_runtime_archive "pharma-backup-archive-$suffix-object-write" \
  --mount "type=bind,src=$work/input,dst=/source,readonly" \
  -- tar -C /source -czf - probe.bin > "$work/archive.tar.gz"
run_runtime_archive "pharma-restore-archive-$suffix-object-list" \
  --mount "type=bind,src=$work,dst=/fixture,readonly" \
  -- tar -tzf /fixture/archive.tar.gz > "$work/listing.txt"
[[ $(<"$work/listing.txt") == probe.bin ]] || exit 1
run_runtime_archive "pharma-restore-archive-$suffix-object-extract" \
  --mount "type=bind,src=$work,dst=/fixture,readonly" \
  --mount "type=bind,src=$work/output,dst=/restore" \
  -- tar -xzf /fixture/archive.tar.gz -C /restore
cmp -- "$work/input/probe.bin" "$work/output/probe.bin"

# Delete only this probe's four known files and empty directories, never a tree.
[[ ! -L "$work" && "$(realpath -e -- "$work")" == "$work" \
  && "$(dirname -- "$work")" == "$parent" \
  && "$(basename -- "$work")" =~ ^pharma-archive-contract\.[A-Za-z0-9]{6}$ \
  && ! -L "$work/input" && ! -L "$work/output" ]] || exit 1
rm -- "$work/input/probe.bin" "$work/output/probe.bin" "$work/archive.tar.gz" "$work/listing.txt"
rmdir -- "$work/input" "$work/output" "$work"
complete=1
python3 - "$revision" "$image" <<'PY'
import json
import sys

print(json.dumps({
    "schema": "x-pharma.runtime-archive-contract.v1", "status": "passed",
    "revision": sys.argv[1], "image": sys.argv[2], "archive_operations": 3,
    "fixture_only": True, "cleanup_verified": True,
}, sort_keys=True))
PY
