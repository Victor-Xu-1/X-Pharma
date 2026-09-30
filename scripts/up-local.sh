#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/up-local.sh [--observed]

Builds PostgreSQL/RDKit and the shared application image sequentially, then
starts the local Compose runtime without triggering Compose parallel builds.

The optional --observed flag enables the local telemetry profile.
EOF
}

observed=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --observed) observed=true ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      usage >&2
      exit 2
      ;;
  esac
  shift
done

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "${root}"

build_timeout=${LOCAL_BUILD_TIMEOUT_SECONDS:-1800}
up_timeout=${LOCAL_UP_TIMEOUT_SECONDS:-300}
force_postgres_build=${FORCE_POSTGRES_BUILD:-false}
[[ ${build_timeout} =~ ^[0-9]+$ && ${build_timeout} -ge 60 && ${build_timeout} -le 7200 ]] || {
  echo "LOCAL_BUILD_TIMEOUT_SECONDS must be an integer between 60 and 7200" >&2
  exit 2
}
[[ ${up_timeout} =~ ^[0-9]+$ && ${up_timeout} -ge 30 && ${up_timeout} -le 1800 ]] || {
  echo "LOCAL_UP_TIMEOUT_SECONDS must be an integer between 30 and 1800" >&2
  exit 2
}
[[ ${force_postgres_build} == true || ${force_postgres_build} == false ]] || {
  echo "FORCE_POSTGRES_BUILD must be true or false" >&2
  exit 2
}

compose=(docker compose -f compose.yaml -f compose.dev.yaml)
if [[ ${observed} == true ]]; then
  compose+=(-f compose.telemetry.yaml)
fi

exec 9>"${TMPDIR:-/tmp}/pharma-intelligence-local-up.lock"
flock -n 9 || {
  echo "Another local runtime build or startup is already running" >&2
  exit 1
}

"${compose[@]}" config --quiet
mapfile -t application_images < <(
  "${compose[@]}" config --images | sed -n '/^pharma-intelligence-api:/p' | sort -u
)
[[ ${#application_images[@]} -eq 1 ]] || {
  echo "Compose must resolve exactly one shared pharma-intelligence-api image" >&2
  exit 1
}
application_image=${application_images[0]}
mapfile -t postgres_images < <(
  "${compose[@]}" config --images | sed -n '/^pharma-postgres-rdkit:/p' | sort -u
)
[[ ${#postgres_images[@]} -eq 1 ]] || {
  echo "Compose must resolve exactly one pharma-postgres-rdkit image" >&2
  exit 1
}
postgres_image=${postgres_images[0]}

if [[ ${force_postgres_build} == true ]] || ! docker image inspect "${postgres_image}" >/dev/null 2>&1; then
  echo "[build] PostgreSQL/RDKit image ${postgres_image}"
  timeout --foreground --kill-after=30s "${build_timeout}s" "${compose[@]}" build postgres
else
  echo "[build] PostgreSQL/RDKit image already present: ${postgres_image}"
fi
echo "[build] shared application image ${application_image}"
timeout --foreground --kill-after=30s "${build_timeout}s" \
  docker build -f deploy/api.Dockerfile -t "${application_image}" .
echo "[runtime] starting services without Compose builds and removing retired service containers"
timeout --foreground --kill-after=30s "${up_timeout}s" "${compose[@]}" up -d --no-build --remove-orphans
