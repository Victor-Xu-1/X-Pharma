#!/usr/bin/env bash
set -Eeuo pipefail

umask 077

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
versions_path="$root/deploy/ingestion/versions.env"
container_name="pharma-smb-source-acceptance-$(date -u +%Y%m%d%H%M%S)-$$"
started=0

usage() {
  cat <<'EOF'
Usage: run-smb-source-acceptance.sh

Run the SMB connector against a disposable, digest-pinned real Samba server.
The server requires SMB3 transport encryption and exposes a read-only share.
The test never records the generated account password or credential payload.
EOF
}

case "${1:-}" in
  "") ;;
  --help|-h)
    usage
    exit 0
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac
[[ $# -le 1 ]] || {
  usage >&2
  exit 2
}

for command in docker python3 id realpath; do
  command -v "$command" >/dev/null 2>&1 || {
    echo "required command is unavailable: $command" >&2
    exit 1
  }
done

work_root=$(realpath "${TMPDIR:-/tmp}")
[[ "$work_root" != / && -d "$work_root" ]] || {
  echo "SMB acceptance temporary root must be an existing non-root directory" >&2
  exit 1
}
fixture_uid=$(id -u)
[[ "$fixture_uid" =~ ^[1-9][0-9]*$ ]] || {
  echo "Run SMB acceptance as a non-root host user to preserve private fixture ownership" >&2
  exit 1
}
work=$(mktemp -d "$work_root/pharma-smb-source-acceptance.XXXXXX")

cleanup() {
  status=$?
  trap - EXIT INT TERM
  if [[ $started -eq 1 ]]; then
    docker rm -f "$container_name" >/dev/null 2>&1 || true
  fi
  case "$work" in
    "$work_root"/pharma-smb-source-acceptance.*) rm -rf -- "$work" ;;
    *) echo "refusing to clean unexpected SMB acceptance workspace: $work" >&2 ;;
  esac
  exit "$status"
}
trap cleanup EXIT INT TERM

declare -A versions=()
while IFS= read -r raw_line || [[ -n "$raw_line" ]]; do
  line=${raw_line%%#*}
  [[ -n "$line" ]] || continue
  if [[ ! "$line" =~ ^([A-Z][A-Z0-9_]*)=([^[:space:]]+)$ ]]; then
    echo "invalid SMB acceptance version declaration" >&2
    exit 1
  fi
  versions["${BASH_REMATCH[1]}"]="${BASH_REMATCH[2]}"
done < "$versions_path"
image=${versions[SMB_TEST_SERVER_IMAGE]:-}
[[ "$image" =~ ^ghcr\.io/servercontainers/samba:smbd-only-latest@sha256:[0-9a-f]{64}$ ]] || {
  echo "SMB_TEST_SERVER_IMAGE must be pinned by registry and digest" >&2
  exit 1
}
[[ "${versions[SMB_TEST_SERVER_VERSION]:-}" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || {
  echo "SMB_TEST_SERVER_VERSION must be an exact Samba version" >&2
  exit 1
}

mkdir -p "$work/source"
initial_egfr='EGFR licensed SMB evidence v1'
updated_egfr='EGFR licensed SMB evidence v2'
[[ ${#initial_egfr} -eq ${#updated_egfr} ]] || {
  echo "SMB acceptance fixtures must have identical byte lengths" >&2
  exit 1
}
printf '%s' "$initial_egfr" > "$work/source/egfr.md"
printf 'MAPK licensed SMB evidence' > "$work/source/mapk.md"
timestamp=1784289600
touch -m -d "@$timestamp" "$work/source/egfr.md" "$work/source/mapk.md"

password=$(python3 - <<'PY'
import secrets

print(secrets.token_urlsafe(32))
PY
)

network_args=()
if [[ -n "${SMB_TEST_DOCKER_NETWORK:-}" ]]; then
  network_args+=(--network "$SMB_TEST_DOCKER_NETWORK")
fi

docker run --detach "${network_args[@]}" \
  --name "$container_name" \
  --hostname smb-acceptance \
  --publish 127.0.0.1::445 \
  --env "ACCOUNT_sourceuser=$password" \
  --env "UID_sourceuser=$fixture_uid" \
  --env NETBIOS_DISABLE=true \
  --env FAIL_FAST=1 \
  --env "SAMBA_GLOBAL_CONFIG_server_SPACE_min_SPACE_protocol=SMB3_00" \
  --env "SAMBA_GLOBAL_CONFIG_server_SPACE_smb_SPACE_encrypt=required" \
  --env "SAMBA_VOLUME_CONFIG_research=[research]; path = /shares/research; valid users = sourceuser; guest ok = no; read only = yes; browseable = yes" \
  --volume "$work/source:/shares/research:ro" \
  "$image" >/dev/null
started=1

binding=$(docker port "$container_name" 445/tcp 2>/dev/null || true)
if [[ -z "$binding" ]]; then
  docker logs --tail 100 "$container_name" >&2 || true
  docker inspect "$container_name" --format 'state={{.State.Status}} error={{.State.Error}}' >&2 || true
  echo "SMB acceptance server did not publish TCP port 445" >&2
  exit 1
fi
port=${binding##*:}
deadline=$((SECONDS + 60))
while ! docker exec "$container_name" sh -c 'test -s /etc/samba/smb.conf && pgrep smbd >/dev/null'; do
  if [[ "$(docker inspect --format '{{.State.Running}}' "$container_name" 2>/dev/null || true)" != "true" ]]; then
    docker logs --tail 100 "$container_name" >&2 || true
    echo "SMB acceptance server exited before becoming ready" >&2
    exit 1
  fi
  if (( SECONDS >= deadline )); then
    docker logs --tail 100 "$container_name" >&2 || true
    echo "SMB acceptance server did not become ready" >&2
    exit 1
  fi
  sleep 1
done

server_version=$(docker exec "$container_name" smbd --version | awk '{print $2}')
[[ "$server_version" == "${versions[SMB_TEST_SERVER_VERSION]}" ]] || {
  echo "SMB acceptance server version does not match the pinned manifest" >&2
  exit 1
}
effective_config=$(docker exec "$container_name" testparm -s 2>/dev/null)
grep -Fq 'server min protocol = SMB3' <<<"$effective_config" || {
  echo "SMB acceptance server did not enforce SMB3" >&2
  exit 1
}
grep -Fq 'server smb encrypt = required' <<<"$effective_config" || {
  echo "SMB acceptance server did not require transport encryption" >&2
  exit 1
}
grep -Fq '[research]' <<<"$effective_config" || {
  echo "SMB acceptance research share is missing" >&2
  exit 1
}
read_only=$(docker exec "$container_name" testparm -s --parameter-name='read only' --section-name=research 2>/dev/null)
[[ "${read_only,,}" == "yes" ]] || {
  printf 'effective_read_only=%s\n' "$read_only" >&2
  echo "SMB acceptance share is not read-only" >&2
  exit 1
}

credential_json=$(
  TEST_USERNAME=sourceuser TEST_PASSWORD="$password" python3 - <<'PY'
import json
import os

print(json.dumps({
    "username": os.environ["TEST_USERNAME"],
    "password": os.environ["TEST_PASSWORD"],
    "auth_protocol": "ntlm",
}, separators=(",", ":")))
PY
)

export TEST_SMB_SOURCE_ORIGIN="smb://127.0.0.1:$port"
export TEST_SMB_SOURCE_DIRECTORY="$work/source"
export TEST_SMB_SOURCE_CREDENTIAL_JSON="$credential_json"
export TEST_SMB_SOURCE_FILE_TIMESTAMP="$timestamp"

uv run pytest -m integration tests/test_smb_snapshot_integration.py -q
printf 'smb_source_acceptance=passed\n'
printf 'smb_transport_encryption=required\n'
printf 'smb_share_access=read_only\n'
printf 'smb_test_server_version=%s\n' "$server_version"
