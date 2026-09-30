#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT_DIR"
output_path=""

usage() {
  cat <<'EOF'
Usage: verify-web-vitals-rum.sh [--output FILE]

Send one privacy-bounded authenticated Web Vital through the running gateway,
verify its OpenTelemetry export, and optionally write immutable local evidence.
The report never contains credentials, tenant IDs, user IDs, URLs, or query data.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --output)
      [[ $# -ge 2 ]] || { echo "--output requires a value" >&2; exit 2; }
      output_path=$2
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

for command in docker openssl python3 sha256sum; do
  command -v "$command" >/dev/null 2>&1 || { echo "required command is unavailable: $command" >&2; exit 1; }
done

export COMPOSE_FILE="${COMPOSE_FILE:-compose.yaml:compose.dev.yaml:compose.telemetry.yaml}"
temporary_root=$(mktemp -d -t pharma-web-vitals-rum.XXXXXX)
credentials_path="$temporary_root/credentials.json"
account_created=false
user_id=""
tenant_id=""
pg_user=""
pg_db=""

cleanup_account() {
  if [[ "$account_created" != true || ! "$user_id" =~ ^[0-9a-f-]{36}$ || ! "$tenant_id" =~ ^[0-9a-f-]{36}$ ]]; then
    return
  fi
  docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -v ON_ERROR_STOP=1 \
    -v tenant_id="$tenant_id" -v user_id="$user_id" >/dev/null <<'SQL'
BEGIN;
DELETE FROM audit_events
WHERE tenant_id = :'tenant_id' AND actor_type = 'user' AND actor_id = :'user_id';
DELETE FROM user_sessions
WHERE tenant_id = :'tenant_id' AND user_id = :'user_id';
DELETE FROM users
WHERE tenant_id = :'tenant_id' AND id = :'user_id';
COMMIT;
SQL
  account_created=false
}

cleanup() {
  set +e
  cleanup_account
  if [[ "$temporary_root" == /tmp/pharma-web-vitals-rum.* ]]; then
    rm -rf -- "$temporary_root"
  fi
}
trap cleanup EXIT

pg_user=$(docker compose exec -T postgres printenv POSTGRES_USER | tr -d '\r')
pg_db=$(docker compose exec -T postgres printenv POSTGRES_DB | tr -d '\r')
tenant_id=$(
  docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -At -v ON_ERROR_STOP=1 \
    -c "SELECT id FROM tenants WHERE active IS TRUE ORDER BY created_at, id LIMIT 1"
)
[[ "$tenant_id" =~ ^[0-9a-f-]{36}$ ]] || { echo "an active tenant is required for RUM acceptance" >&2; exit 1; }

marker=$(python3 -c 'import uuid; print(uuid.uuid4().hex)')
user_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
email="rum-$marker@example.test"
password=$(openssl rand -base64 24 | tr -d '\r\n')
umask 077
printf '{"email":"%s","password":"%s","tenant_id":"%s","user_id":"%s"}\n' \
  "$email" "$password" "$tenant_id" "$user_id" >"$credentials_path"

account_created=true
docker compose exec -T api /app/.venv/bin/python -c '
import json
import sys

from pharma_intel.db import get_session_factory, set_tenant_context
from pharma_intel.models import User, UserRole
from pharma_intel.security import hash_password

payload = json.load(sys.stdin)
with get_session_factory()() as session:
    set_tenant_context(session, payload["tenant_id"])
    session.add(
        User(
            id=payload["user_id"],
            tenant_id=payload["tenant_id"],
            email=payload["email"],
            normalized_email=payload["email"],
            display_name="RUM acceptance",
            password_hash=hash_password(payload["password"]),
            role=UserRole.ANALYST,
        )
    )
    session.commit()
' <"$credentials_path"

started_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
collector_log="$temporary_root/collector.log"

matching_export_count() {
  python3 - "$1" <<'PY'
from __future__ import annotations

import re
import sys
from pathlib import Path

required = (
    "device.class: Str(tablet)",
    "navigation.type: Str(prerender)",
    "web_vital.name: Str(ttfb)",
    "web_vital.rating: Str(needs-improvement)",
    "workspace.view: Str(unknown)",
)
required_bounds = [
    16.0,
    50.0,
    100.0,
    200.0,
    500.0,
    800.0,
    1000.0,
    1800.0,
    2500.0,
    4000.0,
    5000.0,
    10000.0,
    30000.0,
    60000.0,
    120000.0,
]
metric_name = ""
service_name = ""
point: list[str] = []
matches: list[int] = []


def finish_point() -> None:
    if not point or metric_name != "pharma.web.vitals.duration" or service_name != "pharma-gateway":
        return
    block = "\n".join(point)
    if not all(marker in block for marker in required):
        return
    bounds = [float(value) for value in re.findall(r"ExplicitBounds #[0-9]+: ([0-9.]+)", block)]
    if bounds != required_bounds:
        return
    count = re.search(r"\bCount: ([0-9]+)\b", block)
    if count:
        matches.append(int(count.group(1)))


for line in Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace").splitlines():
    if "ResourceMetrics #" in line:
        finish_point()
        point = []
        metric_name = ""
        service_name = ""
    if "-> service.name: Str(" in line:
        service_name = line.split("-> service.name: Str(", 1)[1].split(")", 1)[0]
    if "-> Name: " in line:
        finish_point()
        point = []
        metric_name = line.split("-> Name: ", 1)[1].strip()
        continue
    if "HistogramDataPoints #" in line:
        finish_point()
        point = [line]
        continue
    if point:
        point.append(line)
finish_point()
print(matches[-1] if matches else 0)
PY
}

# Capture one full export interval before the request so cumulative metrics
# cannot make a stale sample look like a successful current gateway export.
sleep 6
docker compose logs --since "$started_at" otel-collector >"$collector_log" 2>&1
baseline_count=$(matching_export_count "$collector_log")

request_result=$(
  docker compose exec -T api /app/.venv/bin/python -c '
import json
import sys

import httpx

credentials = json.load(sys.stdin)

with httpx.Client(base_url="http://127.0.0.1:18380", timeout=10.0) as client:
    login = client.post(
        "/api/v1/auth/login",
        json={"email": credentials["email"], "password": credentials["password"]},
    )
    if login.status_code != 200:
        raise SystemExit(f"gateway login failed with status {login.status_code}")
    csrf = client.cookies.get("pharma_csrf", "")
    if not csrf:
        raise SystemExit("gateway login did not issue a CSRF cookie")
    accepted = client.post(
        "/api/v1/workspace/web-vitals",
        headers={"X-CSRF-Token": csrf},
        json={
            "schema_version": 1,
            "samples": [
                {
                    "metric_name": "TTFB",
                    "value": 1234,
                    "rating": "needs-improvement",
                    "route": "unknown",
                    "navigation_type": "prerender",
                    "navigation_sequence": 10000,
                    "viewport_class": "tablet",
                }
            ],
        },
    )
    if accepted.status_code != 202 or accepted.json() != {"schema_version": 1, "accepted_count": 1}:
        raise SystemExit(f"Web Vitals gateway rejected the controlled sample with status {accepted.status_code}")
    logout = client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf})
    if logout.status_code != 204:
        raise SystemExit(f"gateway logout failed with status {logout.status_code}")
print(json.dumps({"accepted_status": accepted.status_code, "logout_status": logout.status_code}, sort_keys=True))
' <"$credentials_path"
)

exported=false
observed_count="$baseline_count"
for _ in {1..10}; do
  docker compose logs --since "$started_at" otel-collector >"$collector_log" 2>&1
  observed_count=$(matching_export_count "$collector_log")
  if (( observed_count > baseline_count )); then
    exported=true
    break
  fi
  sleep 2
done
[[ "$exported" == true ]] || { echo "Web Vitals metric did not reach the OpenTelemetry collector" >&2; exit 1; }
observed_count_delta=$(( observed_count - baseline_count ))

rum_audit_count=$(
  docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -At -v ON_ERROR_STOP=1 \
    -c "SELECT count(*) FROM audit_events WHERE action = 'POST /api/v1/workspace/web-vitals'"
)
[[ "$rum_audit_count" == "0" ]] || { echo "Web Vitals requests unexpectedly expanded the business audit ledger" >&2; exit 1; }

cleanup_account
temporary_account_rows=$(
  docker compose exec -T postgres psql -X -U "$pg_user" -d "$pg_db" -At -v ON_ERROR_STOP=1 \
    -v tenant_id="$tenant_id" -v user_id="$user_id" <<'SQL'
SELECT
  (SELECT count(*) FROM users WHERE tenant_id = :'tenant_id' AND id = :'user_id')
  + (SELECT count(*) FROM user_sessions WHERE tenant_id = :'tenant_id' AND user_id = :'user_id')
  + (SELECT count(*) FROM audit_events
     WHERE tenant_id = :'tenant_id' AND actor_type = 'user' AND actor_id = :'user_id');
SQL
)
[[ "$temporary_account_rows" == "0" ]] || { echo "temporary RUM acceptance account was not fully removed" >&2; exit 1; }

collector_sha256=$(sha256sum "$collector_log" | cut -d' ' -f1)
if [[ -n "$output_path" ]]; then
  output_path=$(realpath -m -- "$output_path")
  mkdir -p -- "$(dirname -- "$output_path")"
  [[ ! -e "$output_path" && ! -L "$output_path" ]] || { echo "refusing to overwrite RUM evidence: $output_path" >&2; exit 1; }
  python3 - "$output_path" "$request_result" "$collector_sha256" "$observed_count_delta" <<'PY'
from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

output = Path(sys.argv[1])
request = json.loads(sys.argv[2])
payload = {
    "schema": "pharma.web-vitals-rum-acceptance.v1",
    "schema_version": 1,
    "generated_at": datetime.now(UTC).isoformat(),
    "status": "passed",
    "production_claim": False,
    "accepted_status": request["accepted_status"],
    "logout_status": request["logout_status"],
    "metric_names": ["pharma.web.vitals.duration"],
    "observed_count_delta": int(sys.argv[4]),
    "bounded_attributes": [
        "device.class",
        "navigation.type",
        "web_vital.name",
        "web_vital.rating",
        "workspace.view",
    ],
    "business_audit_rows": 0,
    "temporary_account_rows": 0,
    "collector_log_sha256": sys.argv[3],
    "credentials_recorded": False,
}
descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2, sort_keys=True)
    handle.write("\n")
    handle.flush()
    os.fsync(handle.fileno())
PY
  printf 'web_vitals_rum_report=%s\n' "$output_path"
fi

echo "WEB_VITALS_RUM status=passed production_claim=false credentials_recorded=false"
