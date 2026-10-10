#!/usr/bin/env bash

# The explicit acceptance exception belongs to both processes that read the
# temporary aliases. It is never valid in production and is reset on cleanup.
assert_browser_projection_environment() {
  docker compose exec -T api python3 -c 'import sys; from pharma_intel.config import get_settings; sys.exit("Browser acceptance cannot run against production" if get_settings().app_env.lower() == "production" else 0)'
}

enter_browser_projection_mode() {
  assert_browser_projection_environment || return 1
  SEARCH_ALLOW_NON_AUTHORITATIVE_PROJECTION=true docker compose up -d --no-deps --force-recreate api >/dev/null || return 1
  api_container_id=$(docker compose ps -q api) || return 1
  [[ -n "$api_container_id" ]] || return 1
  wait_for_browser_container_healthy "$api_container_id" api 30
}

restore_browser_projection_runtime() {
  local run_identifier=$1
  local rebuilt=false
  [[ "$run_identifier" =~ ^[0-9]{14}-[0-9]{5}$ ]] || return 1
  if docker compose run --rm --no-deps worker pharma-search rebuild --build-id "runtime-$run_identifier" >/dev/null; then
    rebuilt=true
  fi
  # Strictness must be restored even when the authoritative rebuild failed.
  SEARCH_ALLOW_NON_AUTHORITATIVE_PROJECTION=false docker compose up -d --no-deps --force-recreate api worker >/dev/null || return 1
  api_container_id=$(docker compose ps -q api) || return 1
  [[ -n "$api_container_id" && "$rebuilt" == true ]] || return 1
  wait_for_worker_healthy || return 1
  wait_for_browser_container_healthy "$api_container_id" api 30
}
