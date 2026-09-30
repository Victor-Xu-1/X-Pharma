#!/usr/bin/env bash
set -euo pipefail

umask 077

backup=${1:-}
if [[ -z "$backup" || $# -ne 1 ]]; then
  echo "usage: $0 BACKUP_DIR" >&2
  exit 2
fi
for command in docker python3 sha256sum realpath openssl cmp; do
  command -v "$command" >/dev/null 2>&1 || {
    echo "required command is unavailable: $command" >&2
    exit 1
  }
done

backup=$(realpath "$backup")
manifest="$backup/manifest.json"
[[ -f "$manifest" && -f "$backup/checksums.sha256" ]] || {
  echo "backup manifest or checksums are missing: $backup" >&2
  exit 1
}
(
  cd "$backup"
  sha256sum --check --strict checksums.sha256 >/dev/null
)

python3 - "$manifest" "$backup" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

manifest_path = Path(sys.argv[1])
backup_path = Path(sys.argv[2])
document = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
required = {
    "postgres.dump",
    "postgres-globals.sql",
    "object-store.tar.gz",
    "markdown-wiki.tar.gz",
    "temporal.dump",
    "temporal-visibility.dump",
}
authority = document.get("authority")
if not isinstance(authority, list):
    raise SystemExit("backup authority is not a list")
missing = required.difference(authority)
if missing:
    raise SystemExit(f"backup authority is incomplete: {sorted(missing)}")
for name in required:
    path = backup_path / name
    if not path.is_file() or path.stat().st_size == 0:
        raise SystemExit(f"backup artifact is empty or missing: {name}")
row_counts = document.get("rowCounts")
if not isinstance(row_counts, dict) or not row_counts:
    raise SystemExit("backup rowCounts are missing")
for table, count in row_counts.items():
    if not isinstance(table, str) or not isinstance(count, int) or count < 0:
        raise SystemExit("backup rowCounts contain invalid data")
PY

postgres_image=$(python3 - "$manifest" <<'PY'
import json
import sys
from pathlib import Path
print(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8-sig"))["postgresImage"])
PY
)
postgres_image_id=$(python3 - "$manifest" <<'PY'
import json
import sys
from pathlib import Path
print(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8-sig"))["postgresImageId"])
PY
)
api_image=$(python3 - "$manifest" <<'PY'
import json
import sys
from pathlib import Path
print(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8-sig"))["apiImage"])
PY
)
api_image_id=$(python3 - "$manifest" <<'PY'
import json
import sys
from pathlib import Path
print(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8-sig"))["apiImageId"])
PY
)
[[ $(docker image inspect "$postgres_image" --format '{{.Id}}') == "$postgres_image_id" ]] || {
  echo "installed PostgreSQL image identity differs from the backup manifest" >&2
  exit 1
}
[[ $(docker image inspect "$api_image" --format '{{.Id}}') == "$api_image_id" ]] || {
  echo "installed API image identity differs from the backup manifest" >&2
  exit 1
}

suffix="$(date +%s)-$$"
container="pharma-restore-smoke-$suffix"
postgres_volume="pharma-restore-smoke-postgres-$suffix"
object_volume="pharma-restore-smoke-object-$suffix"
markdown_volume="pharma-restore-smoke-markdown-$suffix"
temporary_volumes=("$postgres_volume" "$object_volume" "$markdown_volume")
bootstrap_user=restore_admin
bootstrap_password=$(openssl rand -hex 32)
probe_password=$(openssl rand -hex 32)
work_dir=$(mktemp -d)
started_epoch=$(date +%s)

cleanup() {
  docker rm -f "$container" >/dev/null 2>&1 || true
  for volume in "${temporary_volumes[@]}"; do
    case "$volume" in
      pharma-restore-smoke-*) docker volume rm -f "$volume" >/dev/null 2>&1 || true ;;
      *) echo "refusing to clean unexpected restore volume: $volume" >&2 ;;
    esac
  done
  case "$work_dir" in
    /tmp/tmp.*) rm -rf -- "$work_dir" ;;
    *) echo "refusing to clean unexpected restore work directory: $work_dir" >&2 ;;
  esac
}
trap cleanup EXIT INT TERM

for volume in "${temporary_volumes[@]}"; do
  docker volume create "$volume" >/dev/null
done
docker run -d --name "$container" --network none -e POSTGRES_DB=bootstrap -e POSTGRES_USER="$bootstrap_user" -e POSTGRES_PASSWORD="$bootstrap_password" --mount "type=volume,src=$postgres_volume,dst=/var/lib/postgresql" "$postgres_image" >/dev/null

ready=0
for _ in $(seq 1 90); do
  if docker exec "$container" pg_isready -U "$bootstrap_user" -d bootstrap >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 2
done
[[ $ready -eq 1 ]] || {
  echo "isolated restore PostgreSQL did not become ready" >&2
  exit 1
}

for file in postgres-globals.sql postgres.dump temporal.dump temporal-visibility.dump; do
  docker cp "$backup/$file" "$container:/tmp/$file" >/dev/null
  docker exec -u 0 "$container" chown postgres:postgres "/tmp/$file"
done
docker exec "$container" psql -X -U "$bootstrap_user" -d bootstrap -v ON_ERROR_STOP=1 -f /tmp/postgres-globals.sql >/dev/null
for database in pharma_intel temporal temporal_visibility; do
  docker exec "$container" createdb -U "$bootstrap_user" -O pharma_app "$database"
done
docker exec "$container" pg_restore -U "$bootstrap_user" -d pharma_intel --exit-on-error /tmp/postgres.dump >/dev/null
docker exec "$container" pg_restore -U "$bootstrap_user" -d temporal --exit-on-error /tmp/temporal.dump >/dev/null
docker exec "$container" pg_restore -U "$bootstrap_user" -d temporal_visibility --exit-on-error /tmp/temporal-visibility.dump >/dev/null

expected_counts="$work_dir/expected-counts.tsv"
actual_counts="$work_dir/actual-counts.tsv"
python3 - "$manifest" "$expected_counts" <<'PY'
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

document = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8-sig"))
lines: list[str] = []
for table, count in sorted(document["rowCounts"].items()):
    if not re.fullmatch(r"[a-z_][a-z0-9_]*\.[a-z_][a-z0-9_]*", table):
        raise SystemExit(f"unsafe table identifier in manifest: {table}")
    lines.append(f"{table}\t{count}")
Path(sys.argv[2]).write_text("\n".join(lines) + "\n", encoding="utf-8")
PY

table_list=$(docker exec "$container" psql -X -U "$bootstrap_user" -d pharma_intel -At -F $'\t' -v ON_ERROR_STOP=1 -c "SELECT schemaname, tablename FROM pg_tables WHERE schemaname NOT IN ('pg_catalog','information_schema') ORDER BY 1, 2")
: > "$actual_counts"
while IFS=$'\t' read -r schema relation; do
  [[ -n "$schema" && -n "$relation" ]] || continue
  [[ "$schema" =~ ^[a-z_][a-z0-9_]*$ && "$relation" =~ ^[a-z_][a-z0-9_]*$ ]] || {
    echo "unsafe restored table identifier: $schema.$relation" >&2
    exit 1
  }
  count=$(docker exec "$container" psql -X -U "$bootstrap_user" -d pharma_intel -At -v ON_ERROR_STOP=1 -c "SELECT count(*) FROM \"$schema\".\"$relation\"")
  printf '%s.%s\t%s\n' "$schema" "$relation" "$count" >> "$actual_counts"
done <<< "$table_list"
if ! cmp --silent "$expected_counts" "$actual_counts"; then
  echo "restored table inventory or row counts differ from the backup manifest" >&2
  diff -u "$expected_counts" "$actual_counts" >&2 || true
  exit 1
fi

expected_head=$(python3 - "$manifest" <<'PY'
import json
import sys
from pathlib import Path
print(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8-sig"))["alembicHead"])
PY
)
actual_head=$(docker exec "$container" psql -X -U "$bootstrap_user" -d pharma_intel -At -v ON_ERROR_STOP=1 -c 'SELECT version_num FROM alembic_version')
[[ "$actual_head" == "$expected_head" ]] || {
  echo "Alembic head mismatch: expected=$expected_head actual=$actual_head" >&2
  exit 1
}
rdkit_version=$(docker exec "$container" psql -X -U "$bootstrap_user" -d pharma_intel -At -v ON_ERROR_STOP=1 -c "SELECT extversion FROM pg_extension WHERE extname = 'rdkit'")
[[ -n "$rdkit_version" ]] || {
  echo "RDKit extension is missing from the restored database" >&2
  exit 1
}
for temporal_database in temporal temporal_visibility; do
  temporal_tables=$(docker exec "$container" psql -X -U "$bootstrap_user" -d "$temporal_database" -At -v ON_ERROR_STOP=1 -c "SELECT count(*) FROM pg_tables WHERE schemaname NOT IN ('pg_catalog','information_schema')")
  [[ "$temporal_tables" =~ ^[1-9][0-9]*$ ]] || {
    echo "restored $temporal_database database has no application tables" >&2
    exit 1
  }
done

docker exec "$container" psql -X -U "$bootstrap_user" -d pharma_intel -v ON_ERROR_STOP=1 -c "CREATE ROLE restore_probe LOGIN PASSWORD '$probe_password' NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS; GRANT pharma_runtime TO restore_probe" >/dev/null
tenant_signing_secret=$(docker exec "$container" psql -X -U "$bootstrap_user" -d pharma_intel -At -v ON_ERROR_STOP=1 -c "SELECT secret_value FROM platform_private.runtime_secrets WHERE secret_name = 'tenant_context'")
[[ -n "$tenant_signing_secret" ]] || {
  echo "restored tenant-context signing secret is missing" >&2
  exit 1
}
probe_url="postgresql+psycopg://restore_probe:$probe_password@127.0.0.1:5432/pharma_intel"
docker run --rm --network "container:$container" --read-only --tmpfs /tmp -e "DATABASE_URL=$probe_url" -e "TENANT_CONTEXT_SIGNING_SECRET=$tenant_signing_secret" "$api_image" pharma-verify-rls >/dev/null

busybox_image='busybox:1.36.1@sha256:73aaf090f3d85aa34ee199857f03fa3a95c8ede2ffd4cc2cdb5b94e566b11662'
docker image inspect "$busybox_image" >/dev/null
for archive_spec in "object-store.tar.gz:$object_volume" "markdown-wiki.tar.gz:$markdown_volume"; do
  archive=${archive_spec%%:*}
  volume=${archive_spec#*:}
  docker run --rm --read-only --mount "type=bind,src=$backup,dst=/backup,readonly" "$busybox_image" tar -tzf "/backup/$archive" >/dev/null
  docker run --rm --read-only --mount "type=bind,src=$backup,dst=/backup,readonly" --mount "type=volume,src=$volume,dst=/restore" "$busybox_image" tar -xzf "/backup/$archive" -C /restore
done

tables_verified=$(wc -l < "$expected_counts")
duration_seconds=$(( $(date +%s) - started_epoch ))
python3 - "$backup" "$tables_verified" "$actual_head" "$rdkit_version" "$duration_seconds" <<'PY'
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime

backup, tables, head, rdkit, duration = sys.argv[1:]
print(
    json.dumps(
        {
            "schema_version": 1,
            "created_at": datetime.now(UTC).isoformat(),
            "status": "passed",
            "backup": backup,
            "tables_verified": int(tables),
            "alembic_head": head,
            "rdkit_version": rdkit,
            "temporal_databases_restored": 2,
            "rls_probe": "passed",
            "archives_verified": 2,
            "duration_seconds": int(duration),
            "main_runtime_modified": False,
        },
        indent=2,
        sort_keys=True,
    )
)
PY
