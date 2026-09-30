#!/usr/bin/env bash
set -uo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

failures=0
pass() {
  printf '[pass] %s\n' "$1"
}
fail() {
  printf '[fail] %s\n' "$1" >&2
  failures=$((failures + 1))
}
warn() {
  printf '[warn] %s\n' "$1" >&2
}

if grep -qi microsoft /proc/sys/kernel/osrelease 2>/dev/null; then
  pass "WSL kernel detected"
else
  fail "This check must run inside WSL"
fi

resolved_root="$(realpath "$repo_root")"
if [[ "$resolved_root" == /mnt/* ]]; then
  fail "Repository is on a Windows-mounted filesystem: $resolved_root"
else
  pass "Repository is on the WSL Linux filesystem: $resolved_root"
fi

filesystem_type="$(stat -f -c '%T' "$repo_root")"
if [[ "$filesystem_type" == ext2/ext3 || "$filesystem_type" == ext4 ]]; then
  pass "Repository filesystem is Linux-native: $filesystem_type"
else
  fail "Unexpected repository filesystem: $filesystem_type"
fi

if [[ ! -f .env ]]; then
  fail ".env is missing; create it from .env.example"
else
  env_mode="$(stat -c '%a' .env)"
  if [[ "$env_mode" == 600 ]]; then
    pass ".env permissions are 0600"
  else
    fail ".env permissions must be 0600, found $env_mode"
  fi
fi

runtime_user="$(sed -n 's/^POSTGRES_RUNTIME_USER=//p' .env 2>/dev/null | tail -n 1)"
runtime_password="$(sed -n 's/^POSTGRES_RUNTIME_PASSWORD=//p' .env 2>/dev/null | tail -n 1)"
runtime_database_url="$(sed -n 's/^RUNTIME_DATABASE_URL=//p' .env 2>/dev/null | tail -n 1)"
postgres_database="$(sed -n 's/^POSTGRES_DB=//p' .env 2>/dev/null | tail -n 1)"
if [[ ! "$runtime_user" =~ ^[a-z_][a-z0-9_]*$ ]]; then
  fail "POSTGRES_RUNTIME_USER must be explicitly configured as a lowercase PostgreSQL identifier"
elif [[ -z "$runtime_password" || "$runtime_password" == *replace-* || "$runtime_password" == *change-me* || "$runtime_password" == *only-change-me* ]]; then
  fail "POSTGRES_RUNTIME_PASSWORD must be explicitly configured without a placeholder"
elif [[ -z "$runtime_database_url" || -z "$postgres_database" ]]; then
  fail "RUNTIME_DATABASE_URL and POSTGRES_DB must be explicitly configured"
elif ! RUNTIME_DATABASE_URL="$runtime_database_url" POSTGRES_RUNTIME_USER="$runtime_user" \
  POSTGRES_RUNTIME_PASSWORD="$runtime_password" POSTGRES_DB="$postgres_database" \
  python3 - <<'PY'
import os
from urllib.parse import unquote, urlsplit

url = urlsplit(os.environ["RUNTIME_DATABASE_URL"])
valid = (
    url.scheme in {"postgresql", "postgresql+psycopg"}
    and unquote(url.username or "") == os.environ["POSTGRES_RUNTIME_USER"]
    and unquote(url.password or "") == os.environ["POSTGRES_RUNTIME_PASSWORD"]
    and url.hostname == "postgres"
    and (url.port or 5432) == 5432
    and url.path.removeprefix("/") == os.environ["POSTGRES_DB"]
    and bool(url.password)
)
raise SystemExit(0 if valid else 1)
PY
then
  fail "RUNTIME_DATABASE_URL must bind the configured runtime credentials to the Compose PostgreSQL database"
else
  pass "Runtime PostgreSQL identity is explicit and placeholder-free"
fi

if ! python3 - .env <<'PY'
from pathlib import Path
import sys

values: dict[str, str] = {}
for raw_line in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines():
    line = raw_line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, value = line.split("=", 1)
    values[key.strip()] = value.strip()

required = (
    "JWT_SECRET",
    "INTERNAL_SERVICE_JWT_SECRET",
    "TENANT_CONTEXT_SIGNING_SECRET",
    "API_KEY_HASH_SALT",
    "MCP_CURSOR_SIGNING_SECRET",
    "MCP_CORRELATION_HMAC_SECRET",
    "BILLING_STATEMENT_SIGNING_SECRET",
    "EXPORT_MANIFEST_SIGNING_SECRET",
    "PARSER_SERVICE_TOKEN",
)
secrets = [values.get(key, "") for key in required]
weak_markers = ("replace-", "change-me", "only-change-me")
valid = (
    all(len(value.encode("utf-8")) >= 32 for value in secrets)
    and all(not any(marker in value.casefold() for marker in weak_markers) for value in secrets)
    and len(set(secrets)) == len(secrets)
)
raise SystemExit(0 if valid else 1)
PY
then
  fail "Local cryptographic secrets must all be explicit, unique, placeholder-free and at least 32 bytes"
else
  pass "Independent local cryptographic secrets are configured"
fi

if docker info >/dev/null 2>&1; then
  pass "Docker engine is reachable from WSL"
else
  fail "Docker engine is not reachable from WSL"
fi

if docker compose -f compose.yaml -f compose.dev.yaml -f compose.telemetry.yaml config --quiet; then
  pass "Compose base, development and telemetry overlays render"
else
  fail "Compose configuration is invalid"
fi

versions_path="$repo_root/deploy/kubernetes/platform/versions.env"
kubectl_version=$(sed -n 's/^KUBERNETES_VALIDATION_VERSION=//p' "$versions_path")
kubectl_sha256=$(sed -n 's/^KUBECTL_LINUX_AMD64_SHA256=//p' "$versions_path")
if ! kubectl_path=$(command -v kubectl); then
  fail "Pinned Linux kubectl is unavailable; run make wsl-tools"
elif [[ "$kubectl_path" == *.exe ]]; then
  fail "Windows kubectl is not a reproducible WSL dependency; run make wsl-tools"
elif [[ "$(sha256sum "$kubectl_path" | awk '{print $1}')" != "$kubectl_sha256" ]]; then
  fail "kubectl digest differs from the pinned platform contract"
elif ! installed_kubectl_version=$(kubectl version --client -o json 2>/dev/null | python3 -c 'import json,sys; print(json.load(sys.stdin)["clientVersion"]["gitVersion"])'); then
  fail "kubectl client version cannot be inspected"
elif [[ "$installed_kubectl_version" != "v$kubectl_version" ]]; then
  fail "kubectl version must be v$kubectl_version, found $installed_kubectl_version"
else
  pass "Pinned Linux kubectl v$kubectl_version is verified"
fi

for required_ignore in .env manifests/runtime manifests/acceptance backups data; do
  if grep -Fxq "$required_ignore" .dockerignore; then
    pass "Docker context excludes $required_ignore"
  else
    fail "Docker context does not exclude $required_ignore"
  fi
done

source_root="$(sed -n 's/^KNOWLEDGE_SOURCE_ROOT=//p' .env 2>/dev/null | tail -n 1)"
if [[ -z "$source_root" ]]; then
  fail "KNOWLEDGE_SOURCE_ROOT is not configured"
elif [[ -d "$source_root" ]]; then
  pass "Configured source root exists"
else
  warn "Configured source root is currently unavailable; historical data remains intact"
fi

key_dir="$HOME/.config/pharma-intelligence"
key_file="$key_dir/agent-gateway.key"
if [[ -e "$key_file" ]]; then
  [[ "$(stat -c '%a' "$key_dir")" == 700 ]] && pass "MCP key directory permissions are 0700" || fail "MCP key directory must be 0700"
  [[ "$(stat -c '%a' "$key_file")" == 600 ]] && pass "MCP key file permissions are 0600" || fail "MCP key file must be 0600"
else
  warn "External MCP key file is not present; create or rotate it before paid MCP validation"
fi

if ((failures > 0)); then
  printf '%d WSL environment check(s) failed\n' "$failures" >&2
  exit 1
fi
printf 'WSL environment checks passed\n'
