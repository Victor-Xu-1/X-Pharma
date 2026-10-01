#!/usr/bin/env bash
set -euo pipefail

umask 077

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
security_root="$root/deploy/security"
versions_path="$security_root/versions.env"
vex_path="$security_root/api.openvex.json"
output_directory=""
api_image="pharma-intelligence-api:latest"
postgres_image="pharma-postgres-rdkit:18.4-2026.03.3"
ocr_image="pharma-intelligence-ocr:3.5.0-paddle3.3.1"
release_mode=0
risk_acceptance_reference=""
skip_dependency_audit=0
build_network=default

usage() {
  cat <<'EOF'
Usage: run-security-gates.sh [options]

Options:
  --output-directory DIR
  --api-image IMAGE
  --postgres-image IMAGE
  --ocr-image IMAGE
  --release-mode
  --risk-acceptance-reference REF
  --skip-dependency-audit
  --build-network default|host|none
  -h, --help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --output-directory)
      [[ $# -ge 2 ]] || { echo "--output-directory requires a value" >&2; exit 2; }
      output_directory=$2
      shift 2
      ;;
    --api-image)
      [[ $# -ge 2 ]] || { echo "--api-image requires a value" >&2; exit 2; }
      api_image=$2
      shift 2
      ;;
    --postgres-image)
      [[ $# -ge 2 ]] || { echo "--postgres-image requires a value" >&2; exit 2; }
      postgres_image=$2
      shift 2
      ;;
    --ocr-image)
      [[ $# -ge 2 ]] || { echo "--ocr-image requires a value" >&2; exit 2; }
      ocr_image=$2
      shift 2
      ;;
    --release-mode)
      release_mode=1
      shift
      ;;
    --risk-acceptance-reference)
      [[ $# -ge 2 ]] || { echo "--risk-acceptance-reference requires a value" >&2; exit 2; }
      risk_acceptance_reference=$2
      shift 2
      ;;
    --skip-dependency-audit)
      skip_dependency_audit=1
      shift
      ;;
    --build-network)
      [[ $# -ge 2 ]] || { echo "--build-network requires a value" >&2; exit 2; }
      case "$2" in
        default|host|none) build_network=$2 ;;
        *) echo "unsupported build network: $2" >&2; exit 2 ;;
      esac
      shift 2
      ;;
    -h|--help)
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

if [[ $release_mode -eq 1 && $skip_dependency_audit -eq 1 ]]; then
  echo "release mode cannot skip dependency audits" >&2
  exit 2
fi
for command in curl docker flock git python3 realpath sha256sum stat timeout; do
  command -v "$command" >/dev/null 2>&1 || {
    echo "required command is unavailable: $command" >&2
    exit 1
  }
done
if [[ $skip_dependency_audit -eq 0 ]]; then
  for command in uv corepack; do
    command -v "$command" >/dev/null 2>&1 || {
      echo "dependency audit command is unavailable: $command" >&2
      exit 1
    }
  done
  pnpm_spec=$(python3 - "$root/apps/web/package.json" <<'PY'
import json
import re
import sys
from pathlib import Path

value = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8")).get("packageManager")
if not isinstance(value, str) or re.fullmatch(r"pnpm@[0-9]+\.[0-9]+\.[0-9]+", value) is None:
    raise SystemExit("apps/web/package.json must pin packageManager as pnpm@X.Y.Z")
print(value)
PY
)
  pnpm_command=(corepack "$pnpm_spec")
fi

if git_commit=$(git -C "$root" rev-parse --verify HEAD 2>/dev/null); then
  source_state=clean
else
  git_commit=uncommitted-worktree
  source_state=dirty
fi
worktree_status=$(git -C "$root" -c core.quotepath=false status --porcelain=v1 --untracked-files=all)
if [[ -n "$worktree_status" ]]; then
  source_state=dirty
fi
if [[ $release_mode -eq 1 && "$source_state" != clean ]]; then
  echo "release mode requires an existing commit and a clean Git worktree" >&2
  exit 1
fi

run_id=$(date -u +%Y%m%dT%H%M%SZ)
if [[ -z "$output_directory" ]]; then
  output_directory="$root/manifests/runtime/security/$run_id"
fi
mkdir -p "$output_directory"
output_root=$(realpath "$output_directory")
if find "$output_root" -mindepth 1 -maxdepth 1 -print -quit | grep -q .; then
  echo "security output directory must be empty: $output_root" >&2
  exit 1
fi
chmod 700 "$output_root"

declare -A scanner_images=()
while IFS= read -r raw_line || [[ -n "$raw_line" ]]; do
  line=${raw_line%%#*}
  [[ -n "$line" ]] || continue
  if [[ ! "$line" =~ ^([A-Z][A-Z0-9_]*)=([^[:space:]]+@sha256:[0-9a-f]{64})$ ]]; then
    echo "invalid pinned security image declaration: $raw_line" >&2
    exit 1
  fi
  scanner_images["${BASH_REMATCH[1]}"]="${BASH_REMATCH[2]}"
done < "$versions_path"
for required in GITLEAKS_IMAGE SEMGREP_IMAGE SYFT_IMAGE GRYPE_IMAGE; do
  [[ -n "${scanner_images[$required]:-}" ]] || {
    echo "missing $required in $versions_path" >&2
    exit 1
  }
done

checked() {
  local label=$1
  shift
  printf '[security] %s\n' "$label"
  "$@"
}

checked_with_retry() {
  local label=$1
  local attempts=$2
  shift 2
  local attempt
  for ((attempt = 1; attempt <= attempts; attempt++)); do
    printf '[security] %s (attempt %s/%s)\n' "$label" "$attempt" "$attempts"
    if "$@"; then
      return 0
    fi
    if ((attempt == attempts)); then
      printf '[security] %s failed after %s attempts\n' "$label" "$attempts" >&2
      return 1
    fi
    sleep $((attempt * 5))
  done
}

download_https_in_segments() {
  local url=$1
  local output=$2
  local header_file="$staging_root/grype-database.headers"
  local segment_root="$staging_root/grype-database-segments"
  local segment_count=8
  local total_size

  curl "${curl_options[@]}" --head --max-time 60 --output "$header_file" "$url"
  total_size=$(python3 - "$header_file" <<'PY'
from __future__ import annotations

import re
import sys
from pathlib import Path

headers = Path(sys.argv[1]).read_text(encoding="ascii", errors="strict")
lengths = re.findall(r"(?im)^content-length:\s*([0-9]+)\s*$", headers)
if not lengths or re.search(r"(?im)^accept-ranges:\s*bytes\s*$", headers) is None:
    raise SystemExit("Grype database server did not advertise a bounded byte-range archive")
size = int(lengths[-1])
if size <= 0 or size > 2 * 1024 * 1024 * 1024:
    raise SystemExit("Grype database archive size is outside the accepted range")
print(size)
PY
  )
  mkdir -m 700 "$segment_root"

  local segment_size=$(((total_size + segment_count - 1) / segment_count))
  local -a segment_paths=()
  local -a segment_pids=()
  local index start end part
  for ((index = 0; index < segment_count; index += 1)); do
    start=$((index * segment_size))
    ((start < total_size)) || break
    end=$((start + segment_size - 1))
    ((end < total_size)) || end=$((total_size - 1))
    part="$segment_root/segment-$(printf '%02d' "$index")"
    segment_paths+=("$part")
    (
      local http_code actual_size expected_size
      http_code=$(curl "${curl_options[@]}" --max-time 3600 --range "$start-$end" \
        --output "$part" --write-out '%{http_code}' "$url")
      [[ "$http_code" == 206 ]] || {
        echo "Grype database range $start-$end returned HTTP $http_code instead of 206" >&2
        exit 1
      }
      actual_size=$(stat --format='%s' -- "$part")
      expected_size=$((end - start + 1))
      [[ "$actual_size" == "$expected_size" ]] || {
        echo "Grype database range $start-$end has size $actual_size, expected $expected_size" >&2
        exit 1
      }
    ) &
    segment_pids+=("$!")
  done

  local failed=0
  local pid
  for pid in "${segment_pids[@]}"; do
    if ! wait "$pid"; then
      failed=1
    fi
  done
  [[ $failed -eq 0 ]] || return 1

  python3 - "$output" "$total_size" "${segment_paths[@]}" <<'PY'
from __future__ import annotations

import shutil
import sys
from pathlib import Path

output = Path(sys.argv[1])
expected_size = int(sys.argv[2])
parts = [Path(value) for value in sys.argv[3:]]
temporary = output.with_name(f".{output.name}.assembling")
with temporary.open("xb") as destination:
    for part in parts:
        with part.open("rb") as source:
            shutil.copyfileobj(source, destination, length=1024 * 1024)
if temporary.stat().st_size != expected_size:
    temporary.unlink(missing_ok=True)
    raise SystemExit("assembled Grype database archive has an unexpected size")
temporary.replace(output)
PY
}

docker_image_digest() {
  docker image inspect "$1" | python3 -c '
import json
import sys
item = json.load(sys.stdin)[0]
digests = item.get("RepoDigests") or []
print(digests[0] if digests else "local-image@" + item["Id"])
'
}

checked "Docker daemon check" docker version --format '{{.Server.Version}}' >/dev/null
for required in GITLEAKS_IMAGE SEMGREP_IMAGE SYFT_IMAGE GRYPE_IMAGE; do
  image=${scanner_images[$required]}
  if ! docker image inspect "$image" >/dev/null 2>&1; then
    checked "Pull $required" docker pull "$image" >/dev/null
  fi
done
source "$root/scripts/lib/security_staging.sh"
staging_parent=$(realpath -e -- "${TMPDIR:-/tmp}")
staging_root=$(mktemp -d "$staging_parent/pharma-security.XXXXXX")
cleanup() {
  local status=$?
  if ! security_staging_remove "$staging_parent" "$staging_root"; then
    [[ $status -ne 0 ]] || status=1
  fi
  return "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

repo_prefix="$root/"
source_file_count=0
while IFS= read -r -d '' relative_path; do
  [[ -n "$relative_path" && "$relative_path" != /* && "$relative_path" != ../* && "$relative_path" != */../* ]] || {
    echo "unsafe Git path: $relative_path" >&2
    exit 1
  }
  lexical_path=$(realpath -m "$root/$relative_path")
  [[ "$lexical_path" == "$repo_prefix"* ]] || {
    echo "refusing to stage a path outside the repository: $relative_path" >&2
    exit 1
  }
  [[ ! -L "$root/$relative_path" ]] || {
    echo "security staging does not accept symbolic links: $relative_path" >&2
    exit 1
  }
  [[ -f "$lexical_path" ]] || continue
  destination="$staging_root/$relative_path"
  mkdir -p "$(dirname "$destination")"
  cp -- "$lexical_path" "$destination"
  source_file_count=$((source_file_count + 1))
done < <(git -C "$root" -c core.quotepath=false ls-files --cached --others --exclude-standard -z)
[[ $source_file_count -gt 0 ]] || {
  echo "no deliverable source files were staged" >&2
  exit 1
}
chmod -R u=rwX,go= "$staging_root"
read -r manifested_file_count source_tree_sha256 < <(python3 "$root/scripts/source_tree_manifest.py" "$staging_root")
if [[ "$manifested_file_count" != "$source_file_count" ]]; then
  echo "staged source file count changed while computing its manifest" >&2
  exit 1
fi

case "$api_image" in
  *@*) echo "--api-image must be a writable image tag, not a digest reference" >&2; exit 2 ;;
esac
case "$postgres_image" in
  *@*) echo "--postgres-image must be a writable image tag, not a digest reference" >&2; exit 2 ;;
esac
case "$ocr_image" in
  *@*) echo "--ocr-image must be a writable image tag, not a digest reference" >&2; exit 2 ;;
esac
api_build_labels=(
  --label "org.opencontainers.image.revision=$git_commit"
  --label "io.pharma.source-tree-sha256=$source_tree_sha256"
)
checked "Application image build from staged source" docker build \
  --network "$build_network" \
  --file "$staging_root/deploy/api.Dockerfile" \
  --build-arg "DOCKER_LIBRARY_REGISTRY=${DOCKER_LIBRARY_REGISTRY:-public.ecr.aws/docker/library}" \
  "${api_build_labels[@]}" \
  --tag "$api_image" \
  "$staging_root"
revision=$(docker image inspect --format '{{index .Config.Labels "org.opencontainers.image.revision"}}' "$api_image")
image_source_tree=$(docker image inspect --format '{{index .Config.Labels "io.pharma.source-tree-sha256"}}' "$api_image")
[[ "$revision" == "$git_commit" && "$image_source_tree" == "$source_tree_sha256" ]] || {
  echo "application image labels do not match the staged source" >&2
  exit 1
}

ocr_build_labels=(
  --label "org.opencontainers.image.revision=$git_commit"
  --label "io.pharma.source-tree-sha256=$source_tree_sha256"
)
ocr_build_arguments=(--build-arg "DOCKER_LIBRARY_REGISTRY=${DOCKER_LIBRARY_REGISTRY:-public.ecr.aws/docker/library}")
if [[ -n "${OCR_PYPI_INDEX_URL:-}" ]]; then
  [[ "$OCR_PYPI_INDEX_URL" =~ ^https://[A-Za-z0-9._:-]+(/[A-Za-z0-9._~/-]*)?$ ]] || {
    echo "OCR_PYPI_INDEX_URL must be a credential-free HTTPS package index URL" >&2
    exit 2
  }
  ocr_build_arguments+=(--build-arg "OCR_PYPI_INDEX_URL=$OCR_PYPI_INDEX_URL")
fi
checked "OCR image build from staged source" docker build \
  --network "$build_network" \
  --file "$staging_root/services/ocr/Dockerfile" \
  "${ocr_build_arguments[@]}" \
  "${ocr_build_labels[@]}" \
  --tag "$ocr_image" \
  "$staging_root"
ocr_revision=$(docker image inspect --format '{{index .Config.Labels "org.opencontainers.image.revision"}}' "$ocr_image")
ocr_source_tree=$(docker image inspect --format '{{index .Config.Labels "io.pharma.source-tree-sha256"}}' "$ocr_image")
[[ "$ocr_revision" == "$git_commit" && "$ocr_source_tree" == "$source_tree_sha256" ]] || {
  echo "OCR image labels do not match the staged source" >&2
  exit 1
}

postgres_definition_sha256=$(sha256sum "$staging_root/deploy/postgres-rdkit.Dockerfile")
postgres_definition_sha256=${postgres_definition_sha256%% *}
postgres_image_definition=""
if docker image inspect "$postgres_image" >/dev/null 2>&1; then
  postgres_image_definition=$(
    docker image inspect --format '{{index .Config.Labels "io.pharma.build-definition-sha256"}}' "$postgres_image"
  )
fi
if [[ "$postgres_image_definition" != "$postgres_definition_sha256" ]]; then
  postgres_build_arguments=(--build-arg "DOCKER_LIBRARY_REGISTRY=${DOCKER_LIBRARY_REGISTRY:-public.ecr.aws/docker/library}")
  if [[ -n "${APT_HTTP_PROXY:-}" ]]; then
    [[ "$APT_HTTP_PROXY" =~ ^http://[A-Za-z0-9._:-]+$ ]] || {
      echo "APT_HTTP_PROXY must be a credential-free HTTP proxy URL" >&2
      exit 2
    }
    postgres_build_arguments+=(
      --build-arg "APT_HTTP_PROXY=$APT_HTTP_PROXY"
      --build-arg "HTTP_PROXY=$APT_HTTP_PROXY"
      --build-arg "HTTPS_PROXY=$APT_HTTP_PROXY"
    )
  fi
  checked "PostgreSQL/RDKit image build from pinned definition" docker build \
    --network "$build_network" \
    --file "$staging_root/deploy/postgres-rdkit.Dockerfile" \
    "${postgres_build_arguments[@]}" \
    --label "io.pharma.build-definition-sha256=$postgres_definition_sha256" \
    --tag "$postgres_image" \
    "$staging_root"
else
  printf '[security] PostgreSQL/RDKit image definition unchanged: %s\n' "$postgres_image"
fi
postgres_image_definition=$(
  docker image inspect --format '{{index .Config.Labels "io.pharma.build-definition-sha256"}}' "$postgres_image"
)
[[ "$postgres_image_definition" == "$postgres_definition_sha256" ]] || {
    echo "PostgreSQL/RDKit image label does not match its pinned build definition" >&2
    exit 1
}
api_digest=$(docker_image_digest "$api_image")
postgres_digest=$(docker_image_digest "$postgres_image")
ocr_digest=$(docker_image_digest "$ocr_image")

host_uid=$(id -u)
host_gid=$(id -g)
container_user="$host_uid:$host_gid"
scanner_timeout=(timeout --signal=TERM --kill-after=15s 600s)
common_run=(
  "${scanner_timeout[@]}" docker run --rm
  --user "$container_user"
  --env HOME=/tmp
  --env SYFT_CHECK_FOR_APP_UPDATE=false
  --tmpfs /tmp:rw,noexec,nosuid,mode=1777,size=512m
)

checked "Gitleaks clean-source secret scan" "${common_run[@]}" --mount "type=bind,src=$staging_root,dst=/repo,readonly" --mount "type=bind,src=$output_root,dst=/output" "${scanner_images[GITLEAKS_IMAGE]}" detect --source /repo --no-git --redact --config /repo/.gitleaks.toml --gitleaks-ignore-path /repo/.gitleaksignore --report-format json --report-path /output/gitleaks.json

checked "Semgrep application SAST" "${common_run[@]}" --mount "type=bind,src=$staging_root,dst=/repo,readonly" --mount "type=bind,src=$output_root,dst=/output" "${scanner_images[SEMGREP_IMAGE]}" semgrep scan --jobs 1 --error --timeout 30 --metrics off --config p/python --config p/typescript --config p/docker --config p/kubernetes --json-output /output/semgrep.json /repo/src /repo/scripts /repo/apps/web/src /repo/deploy
python3 - "$output_root/semgrep.json" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

report = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
errors = report.get("errors")
results = report.get("results")
if not isinstance(errors, list) or not isinstance(results, list):
    raise SystemExit("Semgrep report does not contain bounded errors and results arrays")
if errors:
    descriptions = sorted(
        {
            str(error.get("type", "unknown"))
            for error in errors
            if isinstance(error, dict)
        }
    )
    raise SystemExit(f"Semgrep report contains scan errors: {', '.join(descriptions) or 'unknown'}")
PY

if [[ $skip_dependency_audit -eq 0 ]]; then
  requirements_path="$output_root/audit-requirements.txt"
  checked "Locked Python dependency export" uv --quiet --directory "$root" export --locked --no-dev --no-emit-project --format requirements-txt --output-file "$requirements_path"
  checked_with_retry "Python dependency vulnerability audit" 3 uv --quiet --directory "$root" run pip-audit --timeout 60 --no-deps --disable-pip --format json --output "$output_root/pip-audit.json" -r "$requirements_path"
  printf '[security] Node dependency vulnerability audit\n'
  if ! "${pnpm_command[@]}" --dir "$root/apps/web" audit --audit-level high --json > "$output_root/pnpm-audit.json"; then
    echo "Node dependency vulnerability audit failed" >&2
    exit 1
  fi
fi

checked "Source CycloneDX and Syft SBOM" "${common_run[@]}" --mount "type=bind,src=$staging_root,dst=/repo,readonly" --mount "type=bind,src=$output_root,dst=/output" "${scanner_images[SYFT_IMAGE]}" dir:/repo --source-name pharma-intelligence-platform-source --output cyclonedx-json=/output/source.cdx.json --output syft-json=/output/source.syft.json

for target in api postgres ocr; do
  case "$target" in
    api) target_image=$api_image ;;
    postgres) target_image=$postgres_image ;;
    ocr) target_image=$ocr_image ;;
  esac
  image_scan_tmp="$staging_root/image-scan-$target"
  mkdir -m 700 "$image_scan_tmp"
  image_archive="$image_scan_tmp/$target.tar"
  checked "$target image deterministic archive export" \
    "${scanner_timeout[@]}" docker save --output "$image_archive" "$target_image"
  checked "$target image CycloneDX and Syft SBOM" \
    "${scanner_timeout[@]}" docker run --rm \
    --user "$container_user" \
    --env HOME=/tmp \
    --env SYFT_CHECK_FOR_APP_UPDATE=false \
    --tmpfs /tmp:rw,noexec,nosuid,mode=1777,size=2g \
    --mount "type=bind,src=$image_scan_tmp,dst=/scan,readonly" \
    --mount "type=bind,src=$output_root,dst=/output" \
    "${scanner_images[SYFT_IMAGE]}" \
    "docker-archive:/scan/$target.tar" \
    --output "cyclonedx-json=/output/$target.cdx.json" \
    --output "syft-json=/output/$target.syft.json"
  rm -rf -- "$image_scan_tmp"
done

grype_image=${scanner_images[GRYPE_IMAGE]%%@*}
grype_version=${grype_image##*:}
grype_version=${grype_version#v}
[[ "$grype_version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || {
  echo "unable to derive the pinned Grype version" >&2
  exit 1
}
grype_cache_root="${XDG_CACHE_HOME:-$HOME/.cache}/pharma-intelligence/grype/$grype_version"
mkdir -p "$grype_cache_root"
grype_cache_root=$(realpath "$grype_cache_root")
[[ "$grype_cache_root" != "/" && ! -L "$grype_cache_root" ]] || {
  echo "unsafe Grype cache directory: $grype_cache_root" >&2
  exit 1
}
chmod 700 "$grype_cache_root"
grype_run=(
  "${scanner_timeout[@]}" docker run --rm --user "$container_user"
  --env HOME=/cache
  --env GRYPE_CHECK_FOR_APP_UPDATE=false
  --env GRYPE_DB_AUTO_UPDATE=false
  --tmpfs /tmp:rw,noexec,nosuid,mode=1777,size=512m
  --mount "type=bind,src=$grype_cache_root,dst=/cache"
)

grype_lock="$grype_cache_root/.db.lock"
exec 8>"$grype_lock"
flock 8
grype_metadata="$staging_root/grype-latest.json"
curl_options=(
  --fail --silent --show-error --location
  --proto "=https" --tlsv1.2 --http1.1
  --ipv4 --retry 3 --retry-all-errors --connect-timeout 15
)
checked "Grype vulnerability database metadata" curl "${curl_options[@]}" --max-time 60 \
  --output "$grype_metadata" https://grype.anchore.io/databases/v6/latest.json
read -r grype_database_archive grype_database_checksum < <(python3 - "$grype_metadata" <<'PY'
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

metadata = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
archive = metadata.get("path")
checksum = metadata.get("checksum")
if metadata.get("status") != "active" or not isinstance(metadata.get("schemaVersion"), str):
    raise SystemExit("Grype database metadata is not active")
if not isinstance(archive, str) or re.fullmatch(r"[A-Za-z0-9._:-]+", archive) is None:
    raise SystemExit("Grype database metadata contains an unsafe archive path")
if not isinstance(checksum, str) or re.fullmatch(r"sha256:[0-9a-f]{64}", checksum) is None:
    raise SystemExit("Grype database metadata contains an invalid checksum")
print(archive, checksum.removeprefix("sha256:"))
PY
)
grype_database_marker="$grype_cache_root/.imported-checksum"
grype_cache_ready=0
if [[ -f "$grype_database_marker" ]] \
  && [[ "$(<"$grype_database_marker")" == "$grype_database_checksum" ]] \
  && "${grype_run[@]}" "${scanner_images[GRYPE_IMAGE]}" db status >/dev/null 2>&1; then
  grype_cache_ready=1
fi
if [[ $grype_cache_ready -eq 0 ]]; then
  grype_database_path="$staging_root/$grype_database_archive"
  checked "Pinned Grype vulnerability database download" download_https_in_segments \
    "https://grype.anchore.io/databases/v6/$grype_database_archive" \
    "$grype_database_path"
  python3 - "$grype_database_path" "$grype_database_checksum" <<'PY'
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

path = Path(sys.argv[1])
expected = sys.argv[2]
digest = hashlib.sha256()
with path.open("rb") as source:
    while chunk := source.read(1024 * 1024):
        digest.update(chunk)
if digest.hexdigest() != expected:
    raise SystemExit("downloaded Grype database checksum does not match metadata")
PY
  checked "Verified Grype vulnerability database import" \
    "${grype_run[@]}" \
    --mount "type=bind,src=$staging_root,dst=/grype-download,readonly" \
    "${scanner_images[GRYPE_IMAGE]}" db import "/grype-download/$grype_database_archive"
  "${grype_run[@]}" "${scanner_images[GRYPE_IMAGE]}" db status >/dev/null
  grype_marker_temporary="$grype_database_marker.$$.tmp"
  printf '%s\n' "$grype_database_checksum" > "$grype_marker_temporary"
  chmod 600 "$grype_marker_temporary"
  mv -f -- "$grype_marker_temporary" "$grype_database_marker"
fi
flock -u 8

checked "API image complete vulnerability inventory with VEX" "${grype_run[@]}" --mount "type=bind,src=$output_root,dst=/output" --mount "type=bind,src=$security_root,dst=/security,readonly" "${scanner_images[GRYPE_IMAGE]}" sbom:/output/api.syft.json --vex /security/api.openvex.json --output json --file /output/api.grype.json
checked "PostgreSQL/RDKit image complete vulnerability inventory" "${grype_run[@]}" --mount "type=bind,src=$output_root,dst=/output" "${scanner_images[GRYPE_IMAGE]}" sbom:/output/postgres.syft.json --output json --file /output/postgres.grype.json
checked "OCR image complete vulnerability inventory with VEX" "${grype_run[@]}" --mount "type=bind,src=$output_root,dst=/output" --mount "type=bind,src=$security_root,dst=/security,readonly" "${scanner_images[GRYPE_IMAGE]}" sbom:/output/ocr.syft.json --vex /security/ocr.openvex.json --output json --file /output/ocr.grype.json
checked "API image actionable High/Critical vulnerability gate" "${grype_run[@]}" --mount "type=bind,src=$output_root,dst=/output" --mount "type=bind,src=$security_root,dst=/security,readonly" "${scanner_images[GRYPE_IMAGE]}" sbom:/output/api.syft.json --vex /security/api.openvex.json --only-fixed --fail-on high --output json --file /output/api.grype-gate.json
checked "PostgreSQL/RDKit image actionable High/Critical vulnerability gate" "${grype_run[@]}" --mount "type=bind,src=$output_root,dst=/output" "${scanner_images[GRYPE_IMAGE]}" sbom:/output/postgres.syft.json --only-fixed --fail-on high --output json --file /output/postgres.grype-gate.json
checked "OCR image actionable High/Critical vulnerability gate" "${grype_run[@]}" --mount "type=bind,src=$output_root,dst=/output" --mount "type=bind,src=$security_root,dst=/security,readonly" "${scanner_images[GRYPE_IMAGE]}" sbom:/output/ocr.syft.json --vex /security/ocr.openvex.json --only-fixed --fail-on high --output json --file /output/ocr.grype-gate.json

api_unresolved=$(python3 - "$output_root/api.grype.json" <<'PY'
import json
import sys
from pathlib import Path
data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
print(sum(item.get("vulnerability", {}).get("severity") in {"High", "Critical"} for item in data.get("matches", [])))
PY
)
postgres_unresolved=$(python3 - "$output_root/postgres.grype.json" <<'PY'
import json
import sys
from pathlib import Path
data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
print(sum(item.get("vulnerability", {}).get("severity") in {"High", "Critical"} for item in data.get("matches", [])))
PY
)
ocr_unresolved=$(python3 - "$output_root/ocr.grype.json" <<'PY'
import json
import sys
from pathlib import Path
data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
print(sum(item.get("vulnerability", {}).get("severity") in {"High", "Critical"} for item in data.get("matches", [])))
PY
)
if [[ $release_mode -eq 1 && $((api_unresolved + postgres_unresolved + ocr_unresolved)) -gt 0 && -z "$risk_acceptance_reference" ]]; then
  echo "release mode requires --risk-acceptance-reference when unresolved High/Critical findings remain" >&2
  exit 1
fi
final_worktree_status=$(git -C "$root" -c core.quotepath=false status --porcelain=v1 --untracked-files=all)
if [[ -n "$final_worktree_status" ]]; then
  source_state=dirty
fi
if [[ $release_mode -eq 1 && "$source_state" != clean ]]; then
  echo "release mode worktree changed while security evidence was being generated" >&2
  exit 1
fi


python3 - "$output_root/evidence-manifest.json" "$versions_path" "$git_commit" "$source_state" "$source_file_count" "$source_tree_sha256" "$api_digest" "$postgres_digest" "$ocr_digest" "$postgres_definition_sha256" "$api_unresolved" "$postgres_unresolved" "$ocr_unresolved" "$release_mode" "$risk_acceptance_reference" <<'PY'
from __future__ import annotations

import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

(
    output,
    versions,
    git_commit,
    source_state,
    source_count,
    source_tree_sha256,
    api_digest,
    postgres_digest,
    ocr_digest,
    postgres_definition_sha256,
    api_unresolved,
    postgres_unresolved,
    ocr_unresolved,
    release_mode,
    risk_reference,
) = sys.argv[1:]
tools: dict[str, str] = {}
for raw_line in Path(versions).read_text(encoding="utf-8").splitlines():
    line = raw_line.split("#", 1)[0].strip()
    if not line:
        continue
    name, image = line.split("=", 1)
    if not re.fullmatch(r"[A-Z][A-Z0-9_]*", name):
        raise SystemExit(f"invalid scanner name: {name}")
    tools[name] = image
manifest = {
    "schema_version": 1,
    "generated_at": datetime.now(UTC).isoformat(),
    "git_commit": git_commit,
    "git_worktree_state": source_state,
    "source_file_count": int(source_count),
    "source_tree_sha256": source_tree_sha256,
    "targets": {"api": api_digest, "postgres": postgres_digest, "ocr": ocr_digest},
    "target_build_inputs": {
        "api": {"git_commit": git_commit, "source_tree_sha256": source_tree_sha256},
        "postgres": {"definition_sha256": postgres_definition_sha256},
        "ocr": {"git_commit": git_commit, "source_tree_sha256": source_tree_sha256},
    },
    "tools": tools,
    "policies": {
        "secret_scan": "gitleaks-exact-fingerprint-review",
        "sast_scope": ["src", "scripts", "apps/web/src", "deploy"],
        "vulnerability_threshold": "high",
        "actionable_gate": "high-critical-with-upstream-fix",
        "unresolved_high_critical": {
            "api": int(api_unresolved),
            "postgres": int(postgres_unresolved),
            "ocr": int(ocr_unresolved),
        },
        "release_mode": release_mode == "1",
        "risk_acceptance_reference": risk_reference,
        "vex": {
            "api": "deploy/security/api.openvex.json",
            "ocr": "deploy/security/ocr.openvex.json",
        },
    },
}
Path(output).write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

find "$output_root" -type d -exec chmod 700 {} +
find "$output_root" -type f -exec chmod 600 {} +
printf '[security] All gates passed. Evidence: %s\n' "$output_root"
