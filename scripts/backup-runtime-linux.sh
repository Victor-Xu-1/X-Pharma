#!/usr/bin/env bash
set -euo pipefail

umask 077

usage() {
  cat <<'EOF'
Usage: backup-runtime-linux.sh [--output-root DIR] [--project-name NAME]

Create an atomic, checksummed backup of the local WSL runtime. The script
does not stop services or modify source volumes. It fails if authoritative
table counts change while the snapshot set is being captured.
EOF
}

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
output_root="$root/backups"
project_name="${COMPOSE_PROJECT_NAME:-pharma-intelligence}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --output-root)
      [[ $# -ge 2 ]] || { echo "--output-root requires a value" >&2; exit 2; }
      output_root=$2
      shift 2
      ;;
    --project-name)
      [[ $# -ge 2 ]] || { echo "--project-name requires a value" >&2; exit 2; }
      project_name=$2
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

[[ "$project_name" =~ ^[a-z0-9][a-z0-9_-]*$ ]] || {
  echo "unsafe Compose project name: $project_name" >&2
  exit 2
}
for command in docker python3 sha256sum realpath flock cmp; do
  command -v "$command" >/dev/null 2>&1 || {
    echo "required command is unavailable: $command" >&2
    exit 1
  }
done

mkdir -p "$output_root"
output_root=$(realpath "$output_root")
chmod 700 "$output_root"
exec 9>"$output_root/.backup.lock"
flock -n 9 || {
  echo "another runtime backup is already running for $output_root" >&2
  exit 1
}

stamp=$(date -u +%Y%m%d-%H%M%S)
backup_dir="$output_root/runtime-$stamp"
partial_dir="$output_root/.runtime-$stamp-$$.partial"
[[ ! -e "$backup_dir" && ! -e "$partial_dir" ]] || {
  echo "backup target already exists for timestamp $stamp" >&2
  exit 1
}
mkdir -m 700 "$partial_dir"

completed=0
cleanup() {
  if [[ $completed -ne 1 && -d "$partial_dir" ]]; then
    case "$partial_dir" in
      "$output_root"/.runtime-*.partial) rm -rf -- "$partial_dir" ;;
      *) echo "refusing to clean unexpected partial path: $partial_dir" >&2 ;;
    esac
  fi
}
trap cleanup EXIT INT TERM

cd "$root"
compose=(
  docker compose
  --project-name "$project_name"
  -f compose.yaml
  -f compose.dev.yaml
  -f compose.telemetry.yaml
)
postgres_container=$("${compose[@]}" ps -q postgres)
api_container=$("${compose[@]}" ps -q api)
[[ -n "$postgres_container" && -n "$api_container" ]] || {
  echo "PostgreSQL and API Compose services must be running" >&2
  exit 1
}
[[ $(docker inspect --format '{{.State.Running}}' "$postgres_container") == true ]] || {
  echo "PostgreSQL Compose service is not running" >&2
  exit 1
}
[[ $(docker inspect --format '{{.State.Running}}' "$api_container") == true ]] || {
  echo "API Compose service is not running" >&2
  exit 1
}

database=$(docker exec "$postgres_container" printenv POSTGRES_DB)
admin_user=$(docker exec "$postgres_container" printenv POSTGRES_USER)
[[ "$database" =~ ^[a-z_][a-z0-9_]*$ && "$admin_user" =~ ^[a-z_][a-z0-9_]*$ ]] || {
  echo "unsafe PostgreSQL identity returned by the runtime" >&2
  exit 1
}
for required_database in "$database" temporal temporal_visibility; do
  exists=$(docker exec "$postgres_container" psql -X -U "$admin_user" -d postgres -At     -v ON_ERROR_STOP=1     -c "SELECT count(*) FROM pg_database WHERE datname = '$required_database'")
  [[ "$exists" == 1 ]] || {
    echo "required PostgreSQL database is missing: $required_database" >&2
    exit 1
  }
done

collect_table_counts() {
  local destination=$1
  local table_list
  table_list=$(docker exec "$postgres_container" psql -X -U "$admin_user" -d "$database" -At     -F $'\t' -v ON_ERROR_STOP=1     -c "SELECT schemaname, tablename FROM pg_tables WHERE schemaname NOT IN ('pg_catalog','information_schema') ORDER BY 1, 2")
  : > "$destination"
  while IFS=$'\t' read -r schema relation; do
    [[ -n "$schema" && -n "$relation" ]] || continue
    [[ "$schema" =~ ^[a-z_][a-z0-9_]*$ && "$relation" =~ ^[a-z_][a-z0-9_]*$ ]] || {
      echo "unsafe table identifier returned by PostgreSQL: $schema.$relation" >&2
      return 1
    }
    count=$(docker exec "$postgres_container" psql -X -U "$admin_user" -d "$database" -At       -v ON_ERROR_STOP=1 -c "SELECT count(*) FROM \"$schema\".\"$relation\"")
    [[ "$count" =~ ^[0-9]+$ ]] || {
      echo "invalid row count for $schema.$relation: $count" >&2
      return 1
    }
    printf '%s.%s\t%s\n' "$schema" "$relation" "$count" >> "$destination"
  done <<< "$table_list"
  [[ -s "$destination" ]] || {
    echo "PostgreSQL table inventory is empty" >&2
    return 1
  }
}

collect_table_counts "$partial_dir/row-counts.before.tsv"
docker exec "$postgres_container" pg_dump -U "$admin_user" -d "$database" -Fc > "$partial_dir/postgres.dump"
docker exec "$postgres_container" pg_dumpall -U "$admin_user" --globals-only > "$partial_dir/postgres-globals.sql"
docker exec "$postgres_container" pg_dump -U "$admin_user" -d temporal -Fc > "$partial_dir/temporal.dump"
docker exec "$postgres_container" pg_dump -U "$admin_user" -d temporal_visibility -Fc   > "$partial_dir/temporal-visibility.dump"
collect_table_counts "$partial_dir/row-counts.after.tsv"
cmp --silent "$partial_dir/row-counts.before.tsv" "$partial_dir/row-counts.after.tsv" || {
  echo "authoritative table counts changed during backup; retry during a quiet or quiesced window" >&2
  exit 1
}
mv "$partial_dir/row-counts.after.tsv" "$partial_dir/row-counts.tsv"
rm -f "$partial_dir/row-counts.before.tsv"

for dump in postgres.dump temporal.dump temporal-visibility.dump; do
  docker exec -i "$postgres_container" pg_restore --list < "$partial_dir/$dump" >/dev/null
done
[[ -s "$partial_dir/postgres-globals.sql" ]] || {
  echo "PostgreSQL globals dump is empty" >&2
  exit 1
}

compose_volume() {
  local logical_name=$1
  local matches
  mapfile -t matches < <(
    docker volume ls -q       --filter "label=com.docker.compose.project=$project_name"       --filter "label=com.docker.compose.volume=$logical_name"
  )
  [[ ${#matches[@]} -eq 1 ]] || {
    echo "expected exactly one Compose volume for $logical_name, found ${#matches[@]}" >&2
    return 1
  }
  printf '%s\n' "${matches[0]}"
}

object_volume=$(compose_volume pharma_object_store)
markdown_volume=$(compose_volume pharma_markdown_wiki)
busybox_image='busybox:1.36.1@sha256:73aaf090f3d85aa34ee199857f03fa3a95c8ede2ffd4cc2cdb5b94e566b11662'
docker image inspect "$busybox_image" >/dev/null
for archive_spec in   "$object_volume:object-store.tar.gz"   "$markdown_volume:markdown-wiki.tar.gz"; do
  volume=${archive_spec%%:*}
  archive=${archive_spec#*:}
  docker run --rm --read-only     --mount "type=volume,src=$volume,dst=/source,readonly"     "$busybox_image" tar -czf - -C /source . > "$partial_dir/$archive"
  docker run --rm --read-only -i "$busybox_image" tar -tzf - < "$partial_dir/$archive" >/dev/null
done

postgres_image=$(docker inspect --format '{{.Config.Image}}' "$postgres_container")
postgres_image_id=$(docker image inspect --format '{{.Id}}' "$postgres_image")
api_image=$(docker inspect --format '{{.Config.Image}}' "$api_container")
api_image_id=$(docker image inspect --format '{{.Id}}' "$api_image")
alembic_head=$(docker exec "$postgres_container" psql -X -U "$admin_user" -d "$database" -At   -v ON_ERROR_STOP=1 -c 'SELECT version_num FROM alembic_version')
docker_server_version=$(docker version --format '{{.Server.Version}}')

python3 -   "$partial_dir/manifest.json"   "$partial_dir/row-counts.tsv"   "$partial_dir"   "$project_name"   "$database"   "$alembic_head"   "$postgres_image"   "$postgres_image_id"   "$api_image"   "$api_image_id"   "$docker_server_version" <<'PY'
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

(
    manifest_path,
    counts_path,
    backup_path,
    project,
    database,
    alembic_head,
    postgres_image,
    postgres_image_id,
    api_image,
    api_image_id,
    docker_server_version,
) = sys.argv[1:]

authority = [
    "postgres.dump",
    "postgres-globals.sql",
    "object-store.tar.gz",
    "markdown-wiki.tar.gz",
    "temporal.dump",
    "temporal-visibility.dump",
]
row_counts: dict[str, int] = {}
for line in Path(counts_path).read_text(encoding="utf-8").splitlines():
    table, count = line.split("\t", 1)
    row_counts[table] = int(count)

backup_dir = Path(backup_path)
manifest = {
    "schemaVersion": 1,
    "createdAtUtc": datetime.now(UTC).isoformat(),
    "project": project,
    "database": database,
    "alembicHead": alembic_head,
    "postgresImage": postgres_image,
    "postgresImageId": postgres_image_id,
    "apiImage": api_image,
    "apiImageId": api_image_id,
    "dockerServerVersion": docker_server_version,
    "rowCounts": row_counts,
    "authority": authority,
    "rebuildable": ["OpenSearch indexes", "Valkey cache"],
    "temporalDatabases": [
        {"name": "temporal", "dump": "temporal.dump"},
        {"name": "temporal_visibility", "dump": "temporal-visibility.dump"},
    ],
    "consistency": {
        "applicationWritesPaused": False,
        "tableCountsStableAcrossCapture": True,
        "scope": "local WSL migration and recovery contract",
    },
    "artifacts": {
        name: {"sizeBytes": (backup_dir / name).stat().st_size}
        for name in authority
    },
}
Path(manifest_path).write_text(
    json.dumps(manifest, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
PY

rm -f "$partial_dir/row-counts.tsv"
(
  cd "$partial_dir"
  sha256sum     postgres.dump     postgres-globals.sql     object-store.tar.gz     markdown-wiki.tar.gz     temporal.dump     temporal-visibility.dump     manifest.json     > checksums.sha256
  sha256sum --check --strict checksums.sha256 >/dev/null
)
chmod 600 "$partial_dir"/*
mv "$partial_dir" "$backup_dir"
completed=1
printf '%s\n' "$backup_dir"
