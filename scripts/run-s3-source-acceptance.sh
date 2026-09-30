#!/usr/bin/env bash
set -Eeuo pipefail

umask 077

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
versions_path="$root/deploy/ingestion/versions.env"
container_name="pharma-s3-source-acceptance-$(date -u +%Y%m%d%H%M%S)-$$"
bucket="pharma-source-acceptance"
started=0

cleanup() {
  status=$?
  trap - EXIT INT TERM
  if [[ $started -eq 1 ]]; then
    docker rm -f "$container_name" >/dev/null 2>&1 || true
  fi
  exit "$status"
}
trap cleanup EXIT INT TERM

for command in docker python3; do
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
    echo "invalid S3 acceptance version declaration" >&2
    exit 1
  fi
  versions["${BASH_REMATCH[1]}"]="${BASH_REMATCH[2]}"
done < "$versions_path"
image=${versions[S3_TEST_SERVER_IMAGE]:-}
[[ "$image" =~ ^docker\.io/chrislusf/seaweedfs:[0-9]+\.[0-9]+@sha256:[0-9a-f]{64}$ ]] || {
  echo "S3_TEST_SERVER_IMAGE must be pinned by tag and digest" >&2
  exit 1
}

read -r access_key secret_key < <(
  python3 - <<'PY'
import secrets
print(f"acceptance-{secrets.token_hex(8)}", secrets.token_urlsafe(32))
PY
)

docker run --detach --rm \
  --name "$container_name" \
  --publish 127.0.0.1::8333 \
  --env "AWS_ACCESS_KEY_ID=$access_key" \
  --env "AWS_SECRET_ACCESS_KEY=$secret_key" \
  --env "S3_BUCKET=$bucket" \
  --security-opt no-new-privileges:true \
  "$image" mini -dir=/data >/dev/null
started=1

binding=$(docker port "$container_name" 8333/tcp)
endpoint="http://127.0.0.1:${binding##*:}"
credential_json=$(
  TEST_ACCESS_KEY="$access_key" TEST_SECRET_KEY="$secret_key" python3 - <<'PY'
import json
import os
print(json.dumps({
    "access_key_id": os.environ["TEST_ACCESS_KEY"],
    "secret_access_key": os.environ["TEST_SECRET_KEY"],
}, separators=(",", ":")))
PY
)

export TEST_S3_SOURCE_ENDPOINT="$endpoint"
export TEST_S3_SOURCE_BUCKET="$bucket"
export TEST_S3_SOURCE_ACCESS_KEY="$access_key"
export TEST_S3_SOURCE_SECRET_KEY="$secret_key"
export TEST_S3_SOURCE_CREDENTIAL_JSON="$credential_json"

uv run python - <<'PY'
import os
import time

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

client = boto3.client(
    "s3",
    endpoint_url=os.environ["TEST_S3_SOURCE_ENDPOINT"],
    region_name="us-east-1",
    aws_access_key_id=os.environ["TEST_S3_SOURCE_ACCESS_KEY"],
    aws_secret_access_key=os.environ["TEST_S3_SOURCE_SECRET_KEY"],
    config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
)
deadline = time.monotonic() + 60
while True:
    try:
        client.head_bucket(Bucket=os.environ["TEST_S3_SOURCE_BUCKET"])
        break
    except (BotoCoreError, ClientError):
        if time.monotonic() >= deadline:
            raise
        time.sleep(1)
client.close()
PY

uv run pytest -m integration tests/test_s3_snapshot_integration.py -q
printf 's3_source_acceptance=passed\n'
printf 's3_test_server_version=%s\n' "${versions[S3_TEST_SERVER_VERSION]}"
