#!/usr/bin/env bash
set -euo pipefail

umask 077

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
source "$root/scripts/lib/runtime_archive_container.sh"
source "$root/scripts/lib/runtime_restore_resources.sh"
project_name="${COMPOSE_PROJECT_NAME:-pharma-intelligence}"
backup=""

usage() {
  cat <<'EOF'
Usage: restore-runtime-linux.sh [--project-name NAME] BACKUP_DIR

Restore an authoritative WSL runtime backup into a clean Compose project.
The command refuses existing project containers or volumes. It restores
PostgreSQL, Temporal, object evidence and Markdown, then verifies exact row
counts, Alembic, RDKit and runtime RLS before retaining the new volumes.
Only this run's nonce-owned resources may be cleaned. Success requires a
clean PostgreSQL shutdown and confirmed temporary-container removal; an
unconfirmed cleanup retains evidence and never publishes a passed receipt.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project-name)
      [[ $# -ge 2 ]] || { echo "--project-name requires a value" >&2; exit 2; }
      project_name=$2
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    -*)
      echo "unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
    *)
      [[ -z "$backup" ]] || { echo "only one BACKUP_DIR is accepted" >&2; exit 2; }
      backup=$1
      shift
      ;;
  esac
done

[[ -n "$backup" ]] || {
  usage >&2
  exit 2
}
[[ "$project_name" =~ ^[a-z0-9][a-z0-9_-]*$ && ${#project_name} -le 48 ]] || {
  echo "unsafe Compose project name: $project_name" >&2
  exit 2
}
for command in docker python3 sha256sum realpath openssl cmp wc mktemp timeout rmdir; do
  command -v "$command" >/dev/null 2>&1 || {
    echo "required command is unavailable: $command" >&2
    exit 1
  }
done
runtime_restore_docker 10 version --format '{{.Server.Version}}' >/dev/null

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
identity=$(python3 "$root/scripts/lib/runtime_backup_manifest.py" "$manifest")
mapfile -t database_records <<< "$identity"
IFS=$'\t' read -r database postgres_admin <<< "${database_records[0]}"

record=$(python3 - "$manifest" "$backup" <<'PY'
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

manifest_path = Path(sys.argv[1])
backup_path = Path(sys.argv[2])
document = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
if document.get("schemaVersion") != 1:
    raise SystemExit("unsupported backup schemaVersion")
required = {
    "postgres.dump",
    "postgres-globals.sql",
    "object-store.tar.gz",
    "markdown-wiki.tar.gz",
    "temporal.dump",
    "temporal-visibility.dump",
}
authority = document.get("authority")
if not isinstance(authority, list) or required.difference(authority):
    raise SystemExit("backup authority is incomplete")
for name in required:
    path = backup_path / name
    if not path.is_file() or path.stat().st_size == 0:
        raise SystemExit(f"backup artifact is empty or missing: {name}")
row_counts = document.get("rowCounts")
if not isinstance(row_counts, dict) or not row_counts:
    raise SystemExit("backup rowCounts are missing")
for table, count in row_counts.items():
    if not re.fullmatch(r"[a-z_][a-z0-9_]*[.][a-z_][a-z0-9_]*", table):
        raise SystemExit(f"unsafe table identifier in manifest: {table}")
    if not isinstance(count, int) or count < 0:
        raise SystemExit(f"invalid row count in manifest: {table}")
database = document.get("database")
head = document.get("alembicHead")
postgres_image = document.get("postgresImage")
postgres_id = document.get("postgresImageId")
api_image = document.get("apiImage")
api_id = document.get("apiImageId")
if not isinstance(database, str) or not re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", database):
    raise SystemExit("invalid business database in manifest")
if not isinstance(head, str) or not re.fullmatch(r"[a-z0-9]+", head):
    raise SystemExit("invalid Alembic head in manifest")
for label, image in (("PostgreSQL", postgres_image), ("API", api_image)):
    if not isinstance(image, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/@:-]+", image):
        raise SystemExit(f"invalid {label} image reference")
for label, image_id in (("PostgreSQL", postgres_id), ("API", api_id)):
    if not isinstance(image_id, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", image_id):
        raise SystemExit(f"invalid {label} image ID")
print("\t".join((database, head, postgres_image, postgres_id, api_image, api_id)))
PY
)
IFS=$'\t' read -r database expected_head postgres_image postgres_image_id api_image api_image_id <<< "$record"
[[ -n "$api_image_id" ]] || {
  echo "backup image identity record is incomplete" >&2
  exit 1
}

ensure_exact_image() {
  local name=$1
  local expected_id=$2
  local label=$3 actual_id
  runtime_restore_docker 5 image inspect "$expected_id" >/dev/null 2>&1 || {
    echo "$label image ID is not installed; load the signed release image first: $expected_id" >&2
    return 1
  }
  if runtime_restore_docker 5 image inspect "$name" >/dev/null 2>&1; then
    actual_id=$(runtime_restore_docker 5 image inspect "$name" --format '{{.Id}}')
    [[ "$actual_id" == "$expected_id" ]] || {
      echo "$label image tag points to a different image: $name" >&2
      return 1
    }
  else
    runtime_restore_docker 10 image tag "$expected_id" "$name"
  fi
}
ensure_exact_image "$postgres_image" "$postgres_image_id" PostgreSQL
ensure_exact_image "$api_image" "$api_image_id" API

busybox_image=$(runtime_archive_image)
if ! runtime_restore_docker 5 image inspect "$busybox_image" >/dev/null 2>&1; then
  echo "required checksummed BusyBox image is absent; load it before offline restore" >&2
  exit 1
fi

compose=(
  runtime_restore_docker 15 compose
  --project-name "$project_name"
  -f "$root/compose.yaml"
  -f "$root/compose.dev.yaml"
  -f "$root/compose.telemetry.yaml"
)
existing_containers=$("${compose[@]}" ps -aq)
if [[ -n "$existing_containers" ]]; then
  echo "refusing to restore while target Compose containers exist: $project_name" >&2
  exit 1
fi

suffix="$(date +%s)-$$"
runtime_restore_resources_init "$project_name" "$suffix" "$postgres_image_id" "$api_image_id"
work_dir=$restore_work_dir
cleanup() {
  local status=$?
  trap - EXIT INT TERM
  if ! runtime_restore_cleanup; then
    printf 'Restore cleanup is incomplete; retained workspace=%s project=%s\n' "$work_dir" "$project_name" >&2
    [[ $status -ne 0 ]] || status=1
  fi
  exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

postgres_volume=${restore_volumes[0]}
object_volume=${restore_volumes[1]}
markdown_volume=${restore_volumes[2]}
redis_volume="${project_name}_pharma_redis_data"
opensearch_volume="${project_name}_pharma_opensearch_data"
authoritative_volumes=("$postgres_volume" "$object_volume" "$markdown_volume")
for volume in "${authoritative_volumes[@]}" "$redis_volume" "$opensearch_volume"; do
  existing_volume=$(runtime_restore_docker 5 volume ls --filter "name=^$volume$" --format '{{.Name}}')
  if [[ -n "$existing_volume" ]]; then
    echo "refusing to overwrite existing Docker volume: $volume" >&2
    exit 1
  fi
done

compose_version=$(runtime_restore_docker 10 compose version --short)
for index in "${!authoritative_volumes[@]}"; do
  runtime_restore_create_volume "$index" "$compose_version"
done

container_name=${restore_containers[0]}
probe_name=${restore_containers[1]}
token=$(openssl rand -hex 6)
bootstrap_user=$postgres_admin
bootstrap_database="restore_$token"
probe_role="restore_probe_$token"
bootstrap_password=$(openssl rand -hex 32)
probe_password=$(openssl rand -hex 32)
started_epoch=$(date +%s)

runtime_restore_assert_volume "$postgres_volume"
container=$(runtime_restore_docker 20 create --pull=never \
  --name "$container_name" \
  --label "io.pharma.runtime-restore-owner=$restore_owner" \
  --network none \
  -e "POSTGRES_DB=$bootstrap_database" \
  -e "POSTGRES_USER=$bootstrap_user" \
  -e "POSTGRES_PASSWORD=$bootstrap_password" \
  --mount "type=volume,src=$postgres_volume,dst=/var/lib/postgresql" \
  "$postgres_image_id")
[[ "$container" =~ ^[a-f0-9]{64}$ ]] || { echo 'Invalid restore PostgreSQL identity' >&2; exit 1; }
runtime_restore_docker 20 start "$container" >/dev/null

ready=0
ready_deadline=$((SECONDS + 180))
while ((SECONDS < ready_deadline)); do
  if runtime_restore_docker 5 exec "$container" pg_isready -U "$bootstrap_user" -d "$bootstrap_database" >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 2
done
[[ $ready -eq 1 ]] || {
  echo "restore PostgreSQL did not become ready" >&2
  exit 1
}

for file in postgres-globals.sql postgres.dump temporal.dump temporal-visibility.dump; do
  runtime_restore_docker 120 cp "$backup/$file" "$container:/tmp/$file" >/dev/null
  runtime_restore_docker 15 exec -u 0 "$container" chown postgres:postgres "/tmp/$file"
done
role_create_count=$(runtime_restore_docker 15 exec "$container" grep -Ec "^CREATE ROLE (\"$bootstrap_user\"|$bootstrap_user);$" /tmp/postgres-globals.sql || true)
[[ "$role_create_count" == 1 ]] || {
  echo "expected exactly one CREATE ROLE statement for the declared PostgreSQL administrator" >&2
  exit 1
}
runtime_restore_docker 15 exec "$container" sh -c \
  "sed -E '/^CREATE ROLE (\"$bootstrap_user\"|$bootstrap_user);$/d' /tmp/postgres-globals.sql > /tmp/postgres-globals-restore.sql"
runtime_restore_docker 300 exec "$container" psql -X -U "$bootstrap_user" -d "$bootstrap_database" \
  -v ON_ERROR_STOP=1 -f /tmp/postgres-globals-restore.sql >/dev/null

for record in "${database_records[@]:1}"; do
  IFS=$'\t' read -r target_database owner dump <<< "$record"
  runtime_restore_docker 30 exec "$container" createdb -U "$bootstrap_user" -O "$owner" "$target_database"
done
runtime_restore_docker 900 exec "$container" pg_restore -U "$bootstrap_user" -d "$database" --exit-on-error /tmp/postgres.dump >/dev/null
runtime_restore_docker 900 exec "$container" pg_restore -U "$bootstrap_user" -d temporal --exit-on-error /tmp/temporal.dump >/dev/null
runtime_restore_docker 900 exec "$container" pg_restore -U "$bootstrap_user" -d temporal_visibility --exit-on-error /tmp/temporal-visibility.dump >/dev/null

expected_counts="$work_dir/expected-counts.tsv"
actual_counts="$work_dir/actual-counts.tsv"
python3 - "$manifest" "$expected_counts" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

document = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8-sig"))
lines = [f"{table}\t{count}" for table, count in sorted(document["rowCounts"].items())]
Path(sys.argv[2]).write_text("\n".join(lines) + "\n", encoding="utf-8")
PY

table_list=$(runtime_restore_docker 30 exec "$container" psql -X -U "$bootstrap_user" -d "$database" -At -F $'\t' \
  -v ON_ERROR_STOP=1 \
  -c "SELECT schemaname, tablename FROM pg_tables WHERE schemaname NOT IN ('pg_catalog','information_schema') ORDER BY 1, 2")
: > "$actual_counts"
while IFS=$'\t' read -r schema relation; do
  [[ -n "$schema" && -n "$relation" ]] || continue
  [[ "$schema" =~ ^[a-z_][a-z0-9_]*$ && "$relation" =~ ^[a-z_][a-z0-9_]*$ ]] || {
    echo "unsafe restored table identifier: $schema.$relation" >&2
    exit 1
  }
  count=$(runtime_restore_docker 60 exec "$container" psql -X -U "$bootstrap_user" -d "$database" -At \
    -v ON_ERROR_STOP=1 -c "SELECT count(*) FROM \"$schema\".\"$relation\"")
  printf '%s.%s\t%s\n' "$schema" "$relation" "$count" >> "$actual_counts"
done <<< "$table_list"
if ! cmp --silent "$expected_counts" "$actual_counts"; then
  echo "restored table inventory or row counts differ from the backup manifest" >&2
  diff -u "$expected_counts" "$actual_counts" >&2 || true
  exit 1
fi

actual_head=$(runtime_restore_docker 15 exec "$container" psql -X -U "$bootstrap_user" -d "$database" -At \
  -v ON_ERROR_STOP=1 -c 'SELECT version_num FROM alembic_version')
[[ "$actual_head" == "$expected_head" ]] || {
  echo "Alembic head mismatch: expected=$expected_head actual=$actual_head" >&2
  exit 1
}
rdkit_version=$(runtime_restore_docker 15 exec "$container" psql -X -U "$bootstrap_user" -d "$database" -At \
  -v ON_ERROR_STOP=1 -c "SELECT extversion FROM pg_extension WHERE extname = 'rdkit'")
[[ -n "$rdkit_version" ]] || {
  echo "RDKit extension is missing from the restored database" >&2
  exit 1
}
rdkit_probe=$(runtime_restore_docker 15 exec "$container" psql -X -U "$bootstrap_user" -d "$database" -At \
  -v ON_ERROR_STOP=1 -c "SELECT mol_to_smiles(mol_from_smiles('CCO'))")
[[ "$rdkit_probe" == CCO ]] || {
  echo "RDKit function probe failed" >&2
  exit 1
}
for temporal_database in temporal temporal_visibility; do
  temporal_tables=$(runtime_restore_docker 30 exec "$container" psql -X -U "$bootstrap_user" -d "$temporal_database" -At \
    -v ON_ERROR_STOP=1 \
    -c "SELECT count(*) FROM pg_tables WHERE schemaname NOT IN ('pg_catalog','information_schema')")
  [[ "$temporal_tables" =~ ^[1-9][0-9]*$ ]] || {
    echo "restored $temporal_database database has no application tables" >&2
    exit 1
  }
done

runtime_restore_docker 30 exec "$container" psql -X -U "$bootstrap_user" -d "$database" -v ON_ERROR_STOP=1 \
  -c "CREATE ROLE $probe_role LOGIN PASSWORD '$probe_password' NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS; GRANT pharma_runtime TO $probe_role" >/dev/null
tenant_signing_secret=$(runtime_restore_docker 15 exec "$container" psql -X -U "$bootstrap_user" -d "$database" -At \
  -v ON_ERROR_STOP=1 \
  -c "SELECT secret_value FROM platform_private.runtime_secrets WHERE secret_name = 'tenant_context'")
[[ -n "$tenant_signing_secret" ]] || {
  echo "restored tenant-context signing secret is missing" >&2
  exit 1
}
probe_url="postgresql+psycopg://$probe_role:$probe_password@127.0.0.1:5432/$database"
probe_container=$(runtime_restore_docker 20 create --pull=never \
  --name "$probe_name" \
  --label "io.pharma.runtime-restore-owner=$restore_owner" \
  --network "container:$container" \
  --read-only \
  --tmpfs /tmp \
  -e "DATABASE_URL=$probe_url" \
  -e "TENANT_CONTEXT_SIGNING_SECRET=$tenant_signing_secret" \
  "$api_image_id" pharma-verify-rls)
[[ "$probe_container" =~ ^[a-f0-9]{64}$ ]] || { echo 'Invalid restore RLS probe identity' >&2; exit 1; }
runtime_restore_docker 180 start --attach "$probe_container" >/dev/null
[[ $(runtime_restore_docker 5 inspect --format '{{.State.Status}} {{.State.ExitCode}}' "$probe_container") == 'exited 0' ]] || {
  echo 'Restore RLS probe did not exit successfully' >&2; exit 1;
}
runtime_restore_docker 30 exec "$container" psql -X -U "$bootstrap_user" -d "$database" -v ON_ERROR_STOP=1 \
  -c "DROP ROLE $probe_role" >/dev/null

for archive_spec in "object-store.tar.gz:$object_volume" "markdown-wiki.tar.gz:$markdown_volume"; do
  archive=${archive_spec%%:*}
  volume=${archive_spec#*:}
  case "$archive" in
    object-store.tar.gz) archive_kind=object ;;
    markdown-wiki.tar.gz) archive_kind=markdown ;;
    *) echo 'Refusing an unknown restore archive' >&2; exit 2 ;;
  esac
  runtime_restore_assert_volume "$volume"
  run_runtime_archive "pharma-restore-archive-$suffix-$archive_kind-list" \
    --mount "type=bind,src=$backup,dst=/backup,readonly" \
    -- tar -tzf "/backup/$archive" >/dev/null
  runtime_restore_assert_volume "$volume"
  run_runtime_archive "pharma-restore-archive-$suffix-$archive_kind-extract" \
    --mount "type=bind,src=$backup,dst=/backup,readonly" \
    --mount "type=volume,src=$volume,dst=/restore" \
    -- tar -xzf "/backup/$archive" -C /restore
done

runtime_restore_docker 30 exec -i "$container" psql -X -U "$bootstrap_user" -d postgres -v ON_ERROR_STOP=1 <<SQL >/dev/null
ALTER DATABASE postgres OWNER TO "$postgres_admin";
ALTER DATABASE template0 OWNER TO "$postgres_admin";
ALTER DATABASE template1 OWNER TO "$postgres_admin";
DROP DATABASE "$bootstrap_database";
SQL

tables_verified=$(wc -l < "$expected_counts")
# Stop the temporary database cleanly, verify both temporary containers are gone,
# and only then promote the three exact owned volumes and publish a passed receipt.
runtime_restore_cleanup preserve
duration_seconds=$(( $(date +%s) - started_epoch ))
report_directory="$root/manifests/runtime/recovery"
mkdir -p "$report_directory"
chmod 700 "$report_directory"
report="$report_directory/restore-$(date -u +%Y%m%dT%H%M%SZ)-$project_name.json"
python3 - \
  "$report" "$backup" "$project_name" "$tables_verified" "$actual_head" "$rdkit_version" \
  "$duration_seconds" "$postgres_image_id" "$api_image_id" \
  "$postgres_volume" "$object_volume" "$markdown_volume" <<'PY'
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

(
    report,
    backup,
    project,
    tables,
    head,
    rdkit,
    duration,
    postgres_image_id,
    api_image_id,
    postgres_volume,
    object_volume,
    markdown_volume,
) = sys.argv[1:]
document = {
    "schema_version": 1,
    "created_at": datetime.now(UTC).isoformat(),
    "status": "passed",
    "cleanup_verified": True,
    "backup": backup,
    "project": project,
    "tables_verified": int(tables),
    "temporal_databases_restored": 2,
    "alembic_head": head,
    "rdkit_version": rdkit,
    "rls_probe": "passed",
    "archives_restored": 2,
    "duration_seconds": int(duration),
    "postgres_image_id": postgres_image_id,
    "api_image_id": api_image_id,
    "volumes": {
        "postgres": postgres_volume,
        "object_store": object_volume,
        "markdown": markdown_volume,
    },
}
path = Path(report)
temporary = path.with_suffix(path.suffix + ".partial")
temporary.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
temporary.replace(path)
PY
chmod 600 "$report"

printf 'restore_status=passed\n'
printf 'project=%s\n' "$project_name"
printf 'tables_verified=%s\n' "$tables_verified"
printf 'alembic_head=%s\n' "$actual_head"
printf 'rdkit_version=%s\n' "$rdkit_version"
printf 'restore_report=%s\n' "$report"
printf 'next_step=run docker compose --project-name %s -f compose.yaml -f compose.dev.yaml -f compose.telemetry.yaml up -d\n' "$project_name"
