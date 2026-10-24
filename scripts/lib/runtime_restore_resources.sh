#!/usr/bin/env bash

# Clean-target recovery promotes verified volumes; isolated smoke cleanup does not.
runtime_restore_docker() {
  local seconds=${1:-}
  [[ "$seconds" =~ ^[1-9][0-9]*$ && ${#seconds} -le 3 && "$seconds" -le 900 ]] || return 2
  shift
  timeout --kill-after=2s "${seconds}s" docker "$@"
}

runtime_restore_resources_init() {
  [[ $# -eq 4 ]] || return 2
  local project=$1 suffix=$2 postgres_image=$3 api_image=$4
  [[ "$project" =~ ^[a-z0-9][a-z0-9_-]*$ && ${#project} -le 48 \
    && "$suffix" =~ ^[1-9][0-9]*-[1-9][0-9]*$ \
    && "$postgres_image" =~ ^sha256:[0-9a-f]{64}$ && "$api_image" =~ ^sha256:[0-9a-f]{64}$ ]] || return 2
  restore_parent=$(realpath -e -- "${TMPDIR:-/tmp}") || return 2
  [[ "$restore_parent" != / && -d "$restore_parent" ]] || return 2
  restore_work_dir=$(mktemp -d "$restore_parent/pharma-runtime-restore.XXXXXX") || return 1
  restore_owner="$(basename -- "$restore_work_dir")-$suffix"
  restore_project=$project
  restore_containers=("pharma-runtime-restore-$suffix" "pharma-runtime-restore-$suffix-rls")
  restore_images=("$postgres_image" "$api_image")
  restore_volume_keys=(pharma_postgres18_data pharma_object_store pharma_markdown_wiki)
  restore_volumes=()
  local key
  for key in "${restore_volume_keys[@]}"; do restore_volumes+=("${project}_$key"); done
  declare -gA restore_volume_identity=()
  restore_preserve=0
  restore_cleaned=0
}

runtime_restore_workspace_is_owned() {
  [[ "$restore_parent" != / && ! -L "$restore_work_dir" && -d "$restore_work_dir" \
    && "$(realpath -e -- "$restore_parent")" == "$restore_parent" \
    && "$(realpath -e -- "$restore_work_dir")" == "$restore_work_dir" \
    && "$(dirname -- "$restore_work_dir")" == "$restore_parent" \
    && "$(basename -- "$restore_work_dir")" =~ ^pharma-runtime-restore\.[A-Za-z0-9]{6}$ ]] || {
    echo 'Refusing an unexpected clean-target restore workspace' >&2; return 2;
  }
}

runtime_restore_assert_volume() {
  local volume=$1 expected found=0 identity name owner created extra recorded
  for expected in "${restore_volumes[@]}"; do
    [[ "$volume" != "$expected" ]] || found=1
  done
  [[ $found -eq 1 ]] || return 2
  identity=$(runtime_restore_docker 5 volume inspect --format \
    '{{.Name}} {{index .Labels "io.pharma.runtime-restore-owner"}} {{.CreatedAt}}' "$volume") || return 1
  read -r name owner created extra <<< "$identity"
  recorded=${restore_volume_identity[$volume]:-}
  [[ "$name" == "$volume" && "$owner" == "$restore_owner" && -n "$created" && -z "$extra" \
    && ( -z "$recorded" || "$recorded" == "$identity" ) ]] || {
    echo "Restore volume ownership or creation identity changed: $volume" >&2; return 1;
  }
  restore_volume_identity[$volume]=$identity
}

runtime_restore_create_volume() {
  local index=${1:-} compose_version=${2:-}
  [[ "$index" =~ ^[012]$ && "$compose_version" =~ ^[A-Za-z0-9.+_-]+$ ]] || return 2
  runtime_restore_docker 15 volume create \
    --label "io.pharma.runtime-restore-owner=$restore_owner" \
    --label "com.docker.compose.project=$restore_project" \
    --label "com.docker.compose.version=$compose_version" \
    --label "com.docker.compose.volume=${restore_volume_keys[$index]}" \
    "${restore_volumes[$index]}" >/dev/null || return 1
  runtime_restore_assert_volume "${restore_volumes[$index]}"
}

runtime_restore_cleanup() {
  local disposition=${1:-remove} inventory id name extra expected_image identity state count=0 volume file
  [[ "$disposition" == remove || "$disposition" == preserve ]] || return 2
  [[ "$restore_cleaned" -ne 1 ]] || return 0
  runtime_restore_workspace_is_owned || return 1
  [[ "$restore_preserve" -ne 1 ]] || disposition=preserve
  inventory=$(runtime_restore_docker 5 container ls -a --no-trunc \
    --filter "label=io.pharma.runtime-restore-owner=$restore_owner" --format '{{.ID}} {{.Names}}') || return 1
  while IFS=' ' read -r id name extra; do
    [[ -n "$id" ]] || continue
    [[ "$id" =~ ^[a-f0-9]{64}$ && -z "$extra" ]] || return 1
    case "$name" in
      "${restore_containers[0]}") expected_image=${restore_images[0]} ;;
      "${restore_containers[1]}") expected_image=${restore_images[1]} ;;
      *) echo 'Refusing an unexpected restore-owned container' >&2; return 1 ;;
    esac
    identity=$(runtime_restore_docker 5 inspect --format \
      '{{.Id}} {{.Name}} {{.Image}} {{index .Config.Labels "io.pharma.runtime-restore-owner"}}' "$id") || return 1
    [[ "$identity" == "$id /$name $expected_image $restore_owner" ]] || return 1
    if [[ "$disposition" == preserve ]]; then
      if [[ "$name" == "${restore_containers[0]}" ]]; then
        runtime_restore_docker 45 stop --time 30 "$id" >/dev/null || return 1
      fi
      state=$(runtime_restore_docker 5 inspect --format '{{.State.Status}} {{.State.ExitCode}}' "$id") || return 1
      [[ "$state" == 'exited 0' ]] || return 1
    fi
    count=$((count + 1))
    runtime_restore_docker 15 rm -f "$id" >/dev/null 2>&1 || true
  done <<< "$inventory"
  [[ "$disposition" != preserve || "$restore_preserve" -eq 1 || $count -eq 2 ]] || return 1
  inventory=$(runtime_restore_docker 5 container ls -a --no-trunc \
    --filter "label=io.pharma.runtime-restore-owner=$restore_owner" --format '{{.ID}} {{.Names}}') || return 1
  [[ -z "$inventory" ]] || return 1

  if [[ "$disposition" == preserve ]]; then
    for volume in "${restore_volumes[@]}"; do runtime_restore_assert_volume "$volume" || return 1; done
    # From here, reporting/workspace failure retains verified data without a passed receipt.
    restore_preserve=1
  else
    inventory=$(runtime_restore_docker 5 volume ls \
      --filter "label=io.pharma.runtime-restore-owner=$restore_owner" --format '{{.Name}}') || return 1
    while IFS= read -r volume; do
      [[ -n "$volume" ]] || continue
      runtime_restore_assert_volume "$volume" || return 1
      # Never force removal: attached volumes must remain protected by the engine.
      runtime_restore_docker 10 volume rm "$volume" >/dev/null 2>&1 || true
    done <<< "$inventory"
    inventory=$(runtime_restore_docker 5 volume ls \
      --filter "label=io.pharma.runtime-restore-owner=$restore_owner" --format '{{.Name}}') || return 1
    [[ -z "$inventory" ]] || return 1
  fi
  for file in expected-counts.tsv actual-counts.tsv; do
    [[ ! -L "$restore_work_dir/$file" && ( ! -e "$restore_work_dir/$file" || -f "$restore_work_dir/$file" ) ]] || return 1
    rm -f -- "$restore_work_dir/$file" || return 1
  done
  rmdir -- "$restore_work_dir" || return 1
  restore_cleaned=1
}
