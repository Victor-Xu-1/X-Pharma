#!/usr/bin/env bash

# The caller owns the explicit Compose command array. Search fixtures must use
# that same project, even when OpenSearch has no published host port.
mcp_fixture_opensearch() {
  local input_mode=${1:?Expected body or none}
  local interactive
  shift
  case "$input_mode" in
    body) interactive=true ;;
    none) interactive=false ;;
    *) echo 'OpenSearch fixture input mode must be body or none' >&2; return 2 ;;
  esac
  "${compose[@]}" exec -T --interactive="$interactive" opensearch curl --disable \
    --connect-timeout 5 --max-time 30 --silent --show-error "$@"
}
