from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:
    from scripts.release_evidence import ReleaseEvidenceError, _atomic_write, _canonical_json
except ModuleNotFoundError as exc:
    if exc.name != "scripts":
        raise
    from release_evidence import (  # type: ignore[no-redef,import-not-found]
        ReleaseEvidenceError,
        _atomic_write,
        _canonical_json,
    )

COMPOSE_FILES = ("compose.yaml", "compose.dev.yaml", "compose.telemetry.yaml")
REQUIRED_SERVICES = ("postgres", "opensearch", "temporal", "parser", "clamav", "worker")
REQUIRED_CONNECTOR_IDS = frozenset(
    {
        "folder-v1",
        "http-manifest-v1",
        "clinicaltrials-gov-v2",
        "pubmed-eutilities-v1",
        "s3-snapshot-v1",
        "sftp-snapshot-v1",
        "smb-snapshot-v1",
    }
)


def _docker_executable() -> str:
    executable = shutil.which("docker")
    if executable is None:
        raise ReleaseEvidenceError("docker executable is unavailable")
    return executable


def _compose_command(repo: Path, *arguments: str) -> list[str]:
    command = [_docker_executable(), "compose"]
    for name in COMPOSE_FILES:
        path = repo / name
        if not path.is_file():
            raise ReleaseEvidenceError(f"missing Compose file: {name}")
        command.extend(("-f", str(path)))
    command.extend(arguments)
    return command


def _run(repo: Path, *arguments: str) -> str:
    try:
        completed = subprocess.run(  # noqa: S603 - executable and arguments are fixed by this module.
            _compose_command(repo, *arguments),
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise ReleaseEvidenceError(f"Compose readiness command failed: {' '.join(arguments)}") from exc
    return completed.stdout.strip()


def _service_state(repo: Path, service: str) -> dict[str, object]:
    container_id = _run(repo, "ps", "-q", service)
    if not container_id or "\n" in container_id:
        raise ReleaseEvidenceError(f"required service is not uniquely deployed: {service}")
    try:
        completed = subprocess.run(  # noqa: S603 - container ID comes from Docker Compose, not user input.
            [_docker_executable(), "inspect", "--format", "{{json .State}}", container_id],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        state = json.loads(completed.stdout)
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        raise ReleaseEvidenceError(f"cannot inspect required service: {service}") from exc
    if not isinstance(state, dict) or state.get("Running") is not True:
        raise ReleaseEvidenceError(f"required service is not running: {service}")
    health = state.get("Health")
    health_status = health.get("Status") if isinstance(health, dict) else "not-configured"
    if health_status not in {"healthy", "not-configured"}:
        raise ReleaseEvidenceError(f"required service is not healthy: {service} ({health_status})")
    return {"service": service, "running": True, "health": health_status}


def _validate_readiness(document: Any) -> dict[str, object]:
    if not isinstance(document, dict) or document.get("schema") != "pharma.ingestion-readiness.v1":
        raise ReleaseEvidenceError("worker returned an invalid ingestion readiness contract")
    if document.get("status") not in {"ready_for_source_registration", "ready_for_ingestion"}:
        raise ReleaseEvidenceError("automatic ingestion platform readiness is blocked")
    if document.get("production_claim") is not False:
        raise ReleaseEvidenceError("readiness evidence attempted to make a production claim")
    if document.get("real_source_automatic_ingestion_verified") is not False:
        raise ReleaseEvidenceError("readiness evidence cannot substitute for real automatic ingestion evidence")
    inventory = document.get("inventory")
    connectors = document.get("connectors")
    runtime = document.get("runtime")
    if not isinstance(inventory, dict) or not isinstance(connectors, list) or not isinstance(runtime, dict):
        raise ReleaseEvidenceError("worker returned incomplete ingestion readiness evidence")
    if inventory.get("blocked_source_count") != 0:
        raise ReleaseEvidenceError("registered sources contain blocking governance failures")
    connector_ids = {connector.get("connector_id") for connector in connectors if isinstance(connector, dict)}
    if (
        connector_ids != REQUIRED_CONNECTOR_IDS
        or len(connectors) != len(REQUIRED_CONNECTOR_IDS)
        or any(
            not isinstance(connector, dict)
            or connector.get("incremental") is not True
            or connector.get("replayable") is not True
            or connector.get("immutable_snapshot_required") is not True
            for connector in connectors
        )
    ):
        raise ReleaseEvidenceError("required automatic source connector capabilities are incomplete")
    checks = runtime.get("checks")
    if not isinstance(checks, list) or any(
        not isinstance(check, dict) or check.get("status") != "pass" for check in checks
    ):
        raise ReleaseEvidenceError("automatic ingestion runtime controls are incomplete")
    return document


def capture(repo: Path, output: Path) -> dict[str, object]:
    _docker_executable()
    services = [_service_state(repo, service) for service in REQUIRED_SERVICES]
    raw_readiness = _run(repo, "exec", "-T", "worker", "pharma-ingest", "readiness")
    try:
        readiness = _validate_readiness(json.loads(raw_readiness))
    except json.JSONDecodeError as exc:
        raise ReleaseEvidenceError("worker returned malformed ingestion readiness JSON") from exc
    report: dict[str, object] = {
        "schema": "pharma.ingestion-platform-readiness-evidence.v1",
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "passed",
        "environment": "local-wsl",
        "production_claim": False,
        "real_source_automatic_ingestion_verified": False,
        "services": services,
        "readiness": readiness,
    }
    _atomic_write(output, _canonical_json(report))
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Capture fail-closed automatic-ingestion platform readiness without fabricating source evidence"
    )
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(arguments: list[str] | None = None) -> int:
    args = _parser().parse_args(arguments)
    try:
        report = capture(args.repo.resolve(), args.output.resolve())
    except ReleaseEvidenceError as exc:
        print(str(exc), flush=True)
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
