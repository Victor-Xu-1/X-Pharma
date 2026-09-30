#!/usr/bin/env bash
set -euo pipefail

umask 077

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$root"

for command in docker uv; do
  command -v "$command" >/dev/null 2>&1 || {
    echo "required command is unavailable: $command" >&2
    exit 1
  }
done
[[ -f .env ]] || {
  echo ".env is required for local PostgreSQL acceptance" >&2
  exit 1
}

set -a
# shellcheck disable=SC1091
source .env
set +a

for variable in POSTGRES_USER POSTGRES_PASSWORD POSTGRES_RUNTIME_USER POSTGRES_RUNTIME_PASSWORD; do
  [[ -n "${!variable:-}" ]] || {
    echo "$variable is required for local PostgreSQL acceptance" >&2
    exit 1
  }
done

compose=(docker compose -f compose.yaml -f compose.dev.yaml -f compose.telemetry.yaml)
postgres_container=$("${compose[@]}" ps -q postgres)
[[ -n "$postgres_container" && "$(docker inspect --format '{{.State.Health.Status}}' "$postgres_container")" == healthy ]] || {
  echo "the local PostgreSQL Compose service must be healthy" >&2
  exit 1
}

database_name="pharma_commercial_test_$(date -u +%Y%m%d%H%M%S)_$$"
cleanup() {
  "${compose[@]}" exec -T postgres \
    dropdb --if-exists --force -U "$POSTGRES_USER" "$database_name" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

"${compose[@]}" exec -T postgres createdb -U "$POSTGRES_USER" "$database_name"

database_url() {
  DB_USER=$1 DB_PASSWORD=$2 DB_NAME=$database_name uv run python -c \
    'import os; from sqlalchemy.engine import URL; print(URL.create("postgresql+psycopg", username=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"], host="127.0.0.1", port=5433, database=os.environ["DB_NAME"]).render_as_string(hide_password=False))'
}

admin_url=$(database_url "$POSTGRES_USER" "$POSTGRES_PASSWORD")
runtime_url=$(database_url "$POSTGRES_RUNTIME_USER" "$POSTGRES_RUNTIME_PASSWORD")

DATABASE_URL=$admin_url uv run alembic upgrade head >/dev/null
DATABASE_URL=$admin_url \
  POSTGRES_RUNTIME_USER=$POSTGRES_RUNTIME_USER \
  POSTGRES_RUNTIME_PASSWORD=$POSTGRES_RUNTIME_PASSWORD \
  uv run pharma-db-provision >/dev/null
DATABASE_URL=$runtime_url \
  TEST_COMMERCIAL_DATABASE_URL=$runtime_url \
  uv run pytest -q tests/test_commercial_postgres.py --no-cov
