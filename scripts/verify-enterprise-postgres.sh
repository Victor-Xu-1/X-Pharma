#!/usr/bin/env bash
set -euo pipefail

umask 077
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$root"

set -a
# shellcheck disable=SC1091
source .env
set +a
for variable in \
  POSTGRES_USER \
  POSTGRES_PASSWORD \
  POSTGRES_RUNTIME_USER \
  POSTGRES_RUNTIME_PASSWORD \
  TENANT_CONTEXT_SIGNING_SECRET; do
  [[ -n "${!variable:-}" ]] || { echo "$variable is required" >&2; exit 1; }
done

compose=(docker compose -f compose.yaml -f compose.dev.yaml -f compose.telemetry.yaml)
python_bin="$root/.venv/bin/python"
alembic_bin="$root/.venv/bin/alembic"
pytest_bin="$root/.venv/bin/pytest"
provision_bin="$root/.venv/bin/pharma-db-provision"
for executable in "$python_bin" "$alembic_bin" "$pytest_bin" "$provision_bin"; do
  [[ -x "$executable" ]] || { echo "Required project executable is missing: $executable" >&2; exit 1; }
done

database_name="pharma_enterprise_test_$(date -u +%Y%m%d%H%M%S)_$$"
cleanup() {
  "${compose[@]}" exec -T postgres dropdb --if-exists --force -U "$POSTGRES_USER" "$database_name" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM
"${compose[@]}" exec -T postgres createdb -U "$POSTGRES_USER" "$database_name"

database_url() {
  DB_USER=$1 DB_PASSWORD=$2 DB_NAME=$database_name "$python_bin" -c \
    'import os; from sqlalchemy.engine import URL; print(URL.create("postgresql+psycopg", username=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"], host="127.0.0.1", port=5433, database=os.environ["DB_NAME"]).render_as_string(hide_password=False))'
}
admin_url=$(database_url "$POSTGRES_USER" "$POSTGRES_PASSWORD")
runtime_url=$(database_url "$POSTGRES_RUNTIME_USER" "$POSTGRES_RUNTIME_PASSWORD")
DATABASE_URL=$admin_url "$alembic_bin" upgrade head >/dev/null
DATABASE_URL=$admin_url POSTGRES_RUNTIME_USER=$POSTGRES_RUNTIME_USER POSTGRES_RUNTIME_PASSWORD=$POSTGRES_RUNTIME_PASSWORD \
  "$provision_bin" >/dev/null
DATABASE_URL=$runtime_url TEST_ENTERPRISE_DATABASE_URL=$runtime_url \
  "$pytest_bin" -q tests/test_enterprise_postgres.py --no-cov
