#!/usr/bin/env bash
set -euo pipefail

umask 077

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$root"
output_path=""
started_epoch=$(date +%s)

usage() {
  cat <<'EOF'
Usage: verify-local-parser.sh [--output FILE]

Verify the live isolated parser protocol, real format parsers, authentication,
digest checks, container resource boundaries, and Docker network isolation.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --output)
      [[ $# -ge 2 ]] || { echo "--output requires a value" >&2; exit 2; }
      output_path=$2
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

for command in docker python3 realpath dirname basename mktemp uv; do
  command -v "$command" >/dev/null 2>&1 || {
    echo "required command is unavailable: $command" >&2
    exit 1
  }
done

compose=(docker compose -f compose.yaml -f compose.dev.yaml -f compose.telemetry.yaml)
for service in worker parser; do
  container=$("${compose[@]}" ps -q "$service")
  [[ -n "$container" && "$(docker inspect --format '{{.State.Running}}' "$container")" == true ]] || {
    echo "required Compose service is not running: $service" >&2
    exit 1
  }
done
parser_container=$("${compose[@]}" ps -q parser)
worker_container=$("${compose[@]}" ps -q worker)
[[ "$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{end}}' "$parser_container")" == healthy ]] || {
  echo "Parser Compose service is not healthy" >&2
  exit 1
}

work=$(mktemp -d -t pharma-parser-acceptance.XXXXXX)
cleanup() {
  case "$work" in
    /tmp/pharma-parser-acceptance.*) rm -rf -- "$work" ;;
    *) echo "refusing to clean unexpected parser acceptance workspace: $work" >&2 ;;
  esac
}
trap cleanup EXIT INT TERM

docker inspect "$parser_container" "$worker_container" > "$work/containers.json"
python3 - "$work/containers.json" "$work/infrastructure.json" <<'PY'
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

containers_path, output_path = map(Path, sys.argv[1:])
parser, worker = json.loads(containers_path.read_text(encoding="utf-8"))
parser_networks = set(parser["NetworkSettings"]["Networks"])
worker_networks = set(worker["NetworkSettings"]["Networks"])
if len(parser_networks) != 1:
    raise SystemExit("parser container must join exactly one network")
network_name = next(iter(parser_networks))
if not network_name.endswith("_parser-sandbox") or network_name not in worker_networks:
    raise SystemExit("parser sandbox network attachment is invalid")
network = json.loads(
    subprocess.run(
        ["docker", "network", "inspect", network_name],
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    ).stdout
)[0]
if network.get("Internal") is not True:
    raise SystemExit("parser Docker network is not internal")
attached_ids = set(network.get("Containers", {}))
expected_ids = {parser["Id"], worker["Id"]}
if attached_ids != expected_ids:
    raise SystemExit("parser Docker network contains an unexpected container")

host = parser["HostConfig"]
if host.get("ReadonlyRootfs") is not True or host.get("PidsLimit") != 64:
    raise SystemExit("parser container filesystem or PID boundary is missing")
if host.get("Memory") != 3 * 1024**3 or host.get("NanoCpus") != 2_000_000_000:
    raise SystemExit("parser container CPU or memory boundary is missing")
if set(host.get("CapDrop") or []) != {"ALL"} or "no-new-privileges:true" not in set(host.get("SecurityOpt") or []):
    raise SystemExit("parser container privilege boundary is missing")

environment_names = {item.partition("=")[0] for item in parser["Config"].get("Env", [])}
required_names = {
    "PARSER_SERVICE_HOST",
    "PARSER_SERVICE_PORT",
    "PARSER_SERVICE_TOKEN",
    "PARSER_SERVICE_MAX_FILE_BYTES",
    "PARSER_SERVICE_MAX_TEXT_CHARS",
    "PARSER_SERVICE_PARSER_TIMEOUT_SECONDS",
    "PARSER_SERVICE_PARSER_CPU_SECONDS",
    "PARSER_SERVICE_PARSER_MEMORY_BYTES",
    "PARSER_SERVICE_MAX_CONCURRENT_PARSES",
    "PARSER_SERVICE_LIMIT_CONCURRENCY",
}
if not required_names <= environment_names:
    raise SystemExit("parser container configuration is incomplete")
for prefix in (
    "AI_",
    "API_KEY_",
    "DATABASE_",
    "HUMAN_",
    "JWT_",
    "MCP_",
    "OBJECT_STORE_",
    "OPENSEARCH_",
    "POSTGRES_",
    "REDIS_",
    "TEMPORAL_",
):
    if any(name.startswith(prefix) for name in environment_names):
        raise SystemExit(f"parser container received forbidden environment capability: {prefix}")

report = {
    "network_internal": True,
    "network_member_roles": ["parser", "worker"],
    "read_only_root_filesystem": True,
    "pids_limit": host["PidsLimit"],
    "memory_limit_bytes": host["Memory"],
    "nano_cpus": host["NanoCpus"],
    "capabilities_dropped": sorted(host["CapDrop"]),
    "parser_secret_scope": sorted(name for name in environment_names if name.startswith("PARSER_SERVICE_")),
}
output_path.write_text(json.dumps(report, sort_keys=True), encoding="utf-8")
PY

"${compose[@]}" exec -T parser python -c \
  'import socket; connected=False
try:
    connection=socket.create_connection(("1.1.1.1", 443), timeout=2); connection.close(); connected=True
except OSError:
    pass
raise SystemExit(1 if connected else 0)'
"${compose[@]}" exec -T worker pharma-parser-probe > "$work/probe.json"
"${compose[@]}" exec -T worker python -m pharma_intel.ingest.parser_resilience_probe capacity \
  > "$work/capacity.json"
"${compose[@]}" exec -T parser python -m pharma_intel.ingest.parser_resilience_probe timeout \
  > "$work/timeout-recovery.json"
"${compose[@]}" exec -T worker python -m pharma_intel.ingest.parser_resilience_probe corpus \
  > "$work/adversarial-corpus.json"
uv run pharma-parser-mtls-probe > "$work/mtls.json"
chmod 600 "$work/probe.json" "$work/infrastructure.json" "$work/capacity.json" \
  "$work/timeout-recovery.json" "$work/adversarial-corpus.json" "$work/mtls.json"

if [[ -n "$output_path" ]]; then
  output_parent=$(dirname -- "$output_path")
  output_name=$(basename -- "$output_path")
  [[ "$output_name" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]] || {
    echo "invalid output filename: $output_name" >&2
    exit 2
  }
  mkdir -p "$output_parent"
  output_parent=$(realpath "$output_parent")
  output_path="$output_parent/$output_name"
fi

duration_seconds=$(( $(date +%s) - started_epoch ))
python3 - "$work/probe.json" "$work/infrastructure.json" "$work/capacity.json" \
  "$work/timeout-recovery.json" "$work/adversarial-corpus.json" "$work/mtls.json" \
  "$output_path" "$duration_seconds" <<'PY'
from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

(
    probe_path,
    infrastructure_path,
    capacity_path,
    timeout_path,
    corpus_path,
    mtls_path,
    output_text,
    duration,
) = sys.argv[1:]
probe = json.loads(Path(probe_path).read_text(encoding="utf-8"))
infrastructure = json.loads(Path(infrastructure_path).read_text(encoding="utf-8"))
capacity = json.loads(Path(capacity_path).read_text(encoding="utf-8"))
timeout_recovery = json.loads(Path(timeout_path).read_text(encoding="utf-8"))
adversarial_corpus = json.loads(Path(corpus_path).read_text(encoding="utf-8"))
mtls = json.loads(Path(mtls_path).read_text(encoding="utf-8"))
documents = probe.get("documents")
if (
    probe.get("schema_version") != 1
    or probe.get("status") != "passed"
    or probe.get("parser_backend") != "service"
    or probe.get("document_count") != 11
    or probe.get("unauthorized_status") != 401
    or probe.get("digest_mismatch_status") != 400
    or probe.get("production_claim") is not False
    or not isinstance(documents, list)
    or {item.get("suffix") for item in documents if isinstance(item, dict)}
    != {".md", ".html", ".docx", ".pptx", ".xlsx", ".pdf", ".sdf", ".mol", ".pdb", ".cif", ".mmcif"}
):
    raise SystemExit("parser protocol acceptance report violates the expected contract")
if (
    infrastructure.get("network_internal") is not True
    or infrastructure.get("network_member_roles") != ["parser", "worker"]
    or infrastructure.get("read_only_root_filesystem") is not True
    or infrastructure.get("pids_limit") != 64
    or infrastructure.get("capabilities_dropped") != ["ALL"]
):
    raise SystemExit("parser infrastructure acceptance report did not pass")
if (
    capacity.get("schema_version") != 1
    or capacity.get("status") != "passed"
    or capacity.get("production_claim") is not False
    or capacity.get("max_concurrent_parses") != 1
    or capacity.get("held_request_status") != 200
    or capacity.get("saturated_request_status") != 429
    or capacity.get("saturated_error_code") != "parser_capacity_exhausted"
    or capacity.get("retry_after_seconds") != "1"
    or capacity.get("recovery_request_status") != 200
    or capacity.get("ready_after_status") != 200
):
    raise SystemExit("parser capacity and recovery acceptance report did not pass")
if (
    timeout_recovery.get("schema_version") != 1
    or timeout_recovery.get("status") != "passed"
    or timeout_recovery.get("production_claim") is not False
    or timeout_recovery.get("timeout_observed") is not True
    or timeout_recovery.get("child_processes_after_timeout") != 0
    or timeout_recovery.get("recovery_parser_name") != "text"
    or not isinstance(timeout_recovery.get("recovery_text_sha256"), str)
    or len(timeout_recovery["recovery_text_sha256"]) != 64
):
    raise SystemExit("parser timeout cleanup and recovery acceptance report did not pass")
corpus_contract = [
    ("office_path_traversal", ".docx"),
    ("office_duplicate_name", ".xlsx"),
    ("office_symbolic_link", ".pptx"),
    ("office_member_fanout", ".docx"),
    ("office_compression_ratio", ".docx"),
    ("office_encrypted", ".docx"),
    ("pdf_encrypted", ".pdf"),
    ("xml_external_entity", ".xml"),
    ("scientific_malformed", ".sdf"),
]
corpus_cases = adversarial_corpus.get("cases")
if (
    adversarial_corpus.get("schema_version") != 1
    or adversarial_corpus.get("status") != "passed"
    or adversarial_corpus.get("production_claim") is not False
    or adversarial_corpus.get("case_count") != len(corpus_contract)
    or adversarial_corpus.get("recovery_status") != 200
    or adversarial_corpus.get("ready_after_status") != 200
    or not isinstance(corpus_cases, list)
    or len(corpus_cases) != len(corpus_contract)
    or [
        (case.get("name"), case.get("suffix"))
        for case in corpus_cases
        if isinstance(case, dict)
    ] != corpus_contract
    or any(
        not isinstance(case, dict)
        or set(case) != {"name", "suffix", "status", "error_code"}
        or case.get("status") != 422
        or case.get("error_code") != "document_parse_rejected"
        for case in corpus_cases
    )
):
    raise SystemExit("parser adversarial corpus acceptance report did not pass")
if (
    mtls.get("schema_version") != 1
    or mtls.get("status") != "passed"
    or mtls.get("production_claim") is not False
    or mtls.get("mutual_tls") is not True
    or mtls.get("valid_client_parse") is not True
    or mtls.get("no_client_certificate_rejected") is not True
    or mtls.get("rogue_client_rejected") is not True
    or mtls.get("untrusted_server_rejected") is not True
):
    raise SystemExit("parser mTLS acceptance report did not pass")

report = {
    "schema": "pharma.local-parser-sandbox-acceptance.v3",
    **probe,
    "schema_version": 3,
    "generated_at": datetime.now(UTC).isoformat(),
    "environment": "local-wsl-isolated-parser",
    "duration_seconds": int(duration),
    "infrastructure": infrastructure,
    "capacity": capacity,
    "timeout_recovery": timeout_recovery,
    "adversarial_corpus": adversarial_corpus,
    "mtls": mtls,
    "outbound_network_blocked": True,
    "credentials_recorded": False,
}
payload = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode()
if output_text:
    output = Path(output_text)
    temporary = output.with_name(f".{output.name}.{os.getpid()}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, output, follow_symlinks=False)
        except FileExistsError as exc:
            raise SystemExit(f"refusing to overwrite parser evidence: {output}") from exc
        directory_fd = os.open(output.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temporary.unlink(missing_ok=True)
sys.stdout.buffer.write(payload)
PY
