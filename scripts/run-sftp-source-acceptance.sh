#!/usr/bin/env bash
set -Eeuo pipefail

umask 077

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
versions_path="$root/deploy/ingestion/versions.env"
container_name="pharma-sftp-source-acceptance-$(date -u +%Y%m%d%H%M%S)-$$"
started=0

usage() {
  cat <<'EOF'
Usage: run-sftp-source-acceptance.sh

Run the SFTP connector against a disposable, digest-pinned real OpenSSH server.
The test uses public-key authentication and never records private credentials.
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

work=$(mktemp -d -t pharma-sftp-source-acceptance.XXXXXX)

cleanup() {
  status=$?
  trap - EXIT INT TERM
  if [[ $started -eq 1 ]]; then
    docker rm -f "$container_name" >/dev/null 2>&1 || true
  fi
  case "$work" in
    /tmp/pharma-sftp-source-acceptance.*) rm -rf -- "$work" ;;
    *) echo "refusing to clean unexpected SFTP acceptance workspace: $work" >&2 ;;
  esac
  exit "$status"
}
trap cleanup EXIT INT TERM

for command in docker python3 ssh-keyscan; do
  command -v "$command" >/dev/null 2>&1 || {
    echo "required command is unavailable: $command" >&2
    exit 1
  }
done

declare -A versions=()
while IFS= read -r raw_line || [[ -n "$raw_line" ]]; do
  line=${raw_line%%#*}
  [[ -n "$line" ]] || continue
  if [[ ! "$line" =~ ^([A-Z][A-Z0-9_]*)=([^[:space:]]+)$ ]]; then
    echo "invalid SFTP acceptance version declaration" >&2
    exit 1
  fi
  versions["${BASH_REMATCH[1]}"]="${BASH_REMATCH[2]}"
done < "$versions_path"
image=${versions[SFTP_TEST_SERVER_IMAGE]:-}
[[ "$image" =~ ^lscr\.io/linuxserver/openssh-server:version-[0-9]+\.[0-9]+_p[0-9]+-r[0-9]+@sha256:[0-9a-f]{64}$ ]] || {
  echo "SFTP_TEST_SERVER_IMAGE must be pinned by version tag and digest" >&2
  exit 1
}

mkdir -p "$work/source"
printf 'EGFR licensed SFTP evidence v1' > "$work/source/egfr.md"
printf 'MAPK licensed SFTP evidence' > "$work/source/mapk.md"
timestamp=1784289600
touch -m -d "@$timestamp" "$work/source/egfr.md" "$work/source/mapk.md"

uv run python - "$work/client_key" "$work/client_key.pub" <<'PY'
from pathlib import Path
import sys
import paramiko

private_path, public_path = map(Path, sys.argv[1:])
key = paramiko.RSAKey.generate(2048)
key.write_private_key_file(str(private_path))
public_path.write_text(f"{key.get_name()} {key.get_base64()}\n", encoding="ascii")
PY
chmod 600 "$work/client_key" "$work/client_key.pub"
public_key=$(<"$work/client_key.pub")

docker run --detach --rm \
  --name "$container_name" \
  --hostname sftp-acceptance \
  --publish 127.0.0.1::2222 \
  --env "PUID=$(id -u)" \
  --env "PGID=$(id -g)" \
  --env TZ=Etc/UTC \
  --env "PUBLIC_KEY=$public_key" \
  --env SUDO_ACCESS=false \
  --env PASSWORD_ACCESS=false \
  --env USER_NAME=source-user \
  --env LOG_STDOUT=true \
  --tmpfs /config:rw,nosuid,nodev \
  --volume "$work/source:/data:ro" \
  "$image" >/dev/null
started=1

binding=$(docker port "$container_name" 2222/tcp)
port=${binding##*:}
known_hosts="$work/known_hosts"
deadline=$((SECONDS + 60))
while [[ ! -s "$known_hosts" ]]; do
  ssh-keyscan -T 2 -p "$port" 127.0.0.1 > "$known_hosts" 2>/dev/null || true
  if (( SECONDS >= deadline )); then
    docker logs --tail 100 "$container_name" >&2 || true
    echo "SFTP acceptance server did not become ready" >&2
    exit 1
  fi
  sleep 1
done
chmod 600 "$known_hosts"

credential_json=$(
  TEST_USERNAME=source-user TEST_PRIVATE_KEY="$work/client_key" python3 - <<'PY'
import json
import os
from pathlib import Path

print(json.dumps({
    "username": os.environ["TEST_USERNAME"],
    "private_key_pem": Path(os.environ["TEST_PRIVATE_KEY"]).read_text(encoding="utf-8"),
}, separators=(",", ":")))
PY
)

export TEST_SFTP_SOURCE_ORIGIN="sftp://127.0.0.1:$port"
export TEST_SFTP_SOURCE_KNOWN_HOSTS="$known_hosts"
export TEST_SFTP_SOURCE_DIRECTORY="$work/source"
export TEST_SFTP_SOURCE_CREDENTIAL_JSON="$credential_json"

uv run pytest -m integration tests/test_sftp_snapshot_integration.py -q
printf 'sftp_source_acceptance=passed\n'
printf 'sftp_test_server_version=%s\n' "${versions[SFTP_TEST_SERVER_VERSION]}"
