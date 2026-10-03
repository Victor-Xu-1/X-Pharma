#!/usr/bin/env bash
set -euo pipefail

umask 077

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
versions_path="$root/deploy/kubernetes/platform/versions.env"
bin_directory=${PHARMA_WSL_BIN_DIR:-"$HOME/.local/bin"}

for command in curl install mktemp mv python3 realpath sha256sum; do
  command -v "$command" >/dev/null 2>&1 || {
    echo "required command is unavailable: $command" >&2
    exit 1
  }
done

declare -A versions=()
while IFS= read -r raw_line || [[ -n "$raw_line" ]]; do
  line=${raw_line%%#*}
  [[ -n "$line" ]] || continue
  if [[ ! "$line" =~ ^([A-Z][A-Z0-9_]*)=([A-Za-z0-9._/@:-]+)$ ]]; then
    echo "invalid platform version declaration: $raw_line" >&2
    exit 1
  fi
  versions["${BASH_REMATCH[1]}"]="${BASH_REMATCH[2]}"
done < "$versions_path"
for required in KUBERNETES_VALIDATION_VERSION KUBECTL_LINUX_AMD64_SHA256; do
  [[ -n "${versions[$required]:-}" ]] || {
    echo "missing $required in $versions_path" >&2
    exit 1
  }
done

version=${versions[KUBERNETES_VALIDATION_VERSION]}
expected_sha256=${versions[KUBECTL_LINUX_AMD64_SHA256]}
[[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ && "$expected_sha256" =~ ^[0-9a-f]{64}$ ]] || {
  echo "invalid pinned kubectl contract" >&2
  exit 1
}

mkdir -p "$bin_directory"
bin_directory=$(realpath "$bin_directory")
target="$bin_directory/kubectl"
if [[ -L "$target" ]]; then
  echo "refusing to replace a symbolic-link kubectl target: $target" >&2
  exit 1
fi

verify_binary() {
  local binary=$1
  local actual_sha256
  local client_version
  actual_sha256=$(sha256sum "$binary" | awk '{print $1}')
  [[ "$actual_sha256" == "$expected_sha256" ]] || return 1
  client_version=$("$binary" version --client -o json | python3 -c 'import json,sys; print(json.load(sys.stdin)["clientVersion"]["gitVersion"])')
  [[ "$client_version" == "v$version" ]]
}

if [[ -f "$target" ]] && verify_binary "$target"; then
  printf '[wsl-tools] kubectl v%s already verified at %s\n' "$version" "$target"
  exit 0
fi

artifact_cache=${PHARMA_WSL_ARTIFACT_CACHE:-"${XDG_CACHE_HOME:-$HOME/.cache}/pharma-intelligence/tools"}
mkdir -p "$artifact_cache"
[[ ! -L "$artifact_cache" ]] || { echo "refusing symbolic-link artifact cache" >&2; exit 1; }
artifact_cache=$(realpath "$artifact_cache")
cached_binary="$artifact_cache/$expected_sha256.kubectl"
[[ ! -L "$cached_binary" ]] || { echo "refusing symbolic-link cached tool" >&2; exit 1; }

install_verified_binary() {
  local binary=$1
  local partial="$target.partial.$$"
  [[ ! -e "$partial" && ! -L "$partial" ]] || { echo "existing partial target preserved" >&2; return 1; }
  verify_binary "$binary" || return 1
  install -m 0755 "$binary" "$partial"
  mv -f -- "$partial" "$target"
  verify_binary "$target"
}

if [[ -f "$cached_binary" ]]; then
  verify_binary "$cached_binary" || { echo "cached kubectl failed pinned digest or version verification" >&2; exit 1; }
  install_verified_binary "$cached_binary"
  printf '[wsl-tools] installed verified cached kubectl v%s at %s\n' "$version" "$target"
  exit 0
fi
if [[ "${PHARMA_WSL_OFFLINE:-false}" == "true" ]]; then
  echo "offline kubectl artifact is unavailable; no network download was attempted" >&2
  exit 1
fi

workspace=$(mktemp -d -t pharma-wsl-tools.XXXXXX)
partial_target="$target.partial.$$"
cleanup() {
  status=$?
  trap - EXIT INT TERM
  rm -f -- "$partial_target"
  case "$workspace" in
    "${TMPDIR:-/tmp}"/pharma-wsl-tools.*) rm -rf -- "$workspace" ;;
    *) echo "refusing to clean unexpected WSL tools workspace: $workspace" >&2 ;;
  esac
  exit "$status"
}
trap cleanup EXIT INT TERM

origin="https://dl.k8s.io/v$version/bin/linux/amd64/kubectl"
curl_args=(--fail --silent --show-error --location --connect-timeout 15 --max-time 180 --retry 2 --retry-all-errors)
printf '[wsl-tools] downloading kubectl v%s\n' "$version"
curl "${curl_args[@]}" "$origin" --output "$workspace/kubectl"
curl "${curl_args[@]}" "$origin.sha256" --output "$workspace/kubectl.sha256"
published_sha256=$(python3 -c 'import pathlib,sys; print(pathlib.Path(sys.argv[1]).read_text(encoding="ascii").strip())' "$workspace/kubectl.sha256")
[[ "$published_sha256" == "$expected_sha256" ]] || {
  echo "published kubectl checksum differs from the pinned platform contract" >&2
  exit 1
}
chmod 0700 "$workspace/kubectl"
verify_binary "$workspace/kubectl" || {
  echo "downloaded kubectl binary failed digest or version verification" >&2
  exit 1
}
cache_partial="$cached_binary.partial.$$"
[[ ! -e "$cache_partial" && ! -L "$cache_partial" ]] || { echo "existing cache partial preserved" >&2; exit 1; }
install -m 0755 "$workspace/kubectl" "$cache_partial"
mv -f -- "$cache_partial" "$cached_binary"
install_verified_binary "$cached_binary" || {
  echo "installed kubectl binary failed post-install verification" >&2
  exit 1
}
printf '[wsl-tools] installed kubectl v%s at %s\n' "$version" "$target"
