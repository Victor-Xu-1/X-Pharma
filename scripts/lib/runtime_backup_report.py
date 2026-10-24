"""Build a source-bound local restore receipt without installed application dependencies."""

from __future__ import annotations

import hashlib
import json
import os
import runpy
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[2]


def load_contract() -> tuple[str, int, Callable[[Mapping[str, object]], int]]:
    # Load the one trusted, stdlib-only module directly: importing pharma_intel
    # would require installed distribution metadata on an otherwise Docker-only host.
    namespace = runpy.run_path(str(ROOT / "src/pharma_intel/platform/backup_contract.py"))
    return (
        cast(str, namespace["BACKUP_RESTORE_SCHEMA"]),
        cast(int, namespace["BACKUP_RESTORE_SCHEMA_VERSION"]),
        cast(Callable[[Mapping[str, object]], int], namespace["validate_backup_restore_report"]),
    )


def load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError("backup/restore metadata must be a JSON object")
    return value


def build_report(
    manifest_path: Path,
    checksums_path: Path,
    restore_path: Path,
    backup: Path,
    authority_root: Path,
    duration: int,
    target_image: str,
) -> dict[str, Any]:
    backup, authority_root = backup.resolve(), authority_root.resolve()
    if manifest_path.resolve() != backup / "manifest.json" or checksums_path.resolve() != backup / "checksums.sha256":
        raise ValueError("backup authority metadata does not belong to its recorded directory")
    try:
        reference = (Path("backups") / backup.relative_to(authority_root)).as_posix()
    except ValueError as exc:
        raise ValueError("backup path escaped the configured backup authority root") from exc
    manifest, restore = load_object(manifest_path), load_object(restore_path)
    if restore.get("status") != "passed" or restore.get("main_runtime_modified") is not False:
        raise ValueError("isolated restore smoke did not pass without modifying the main runtime")
    if restore.get("rls_probe") != "passed" or restore.get("temporal_databases_restored") != 2:
        raise ValueError("restored RLS or Temporal authority verification failed")
    counts = manifest.get("rowCounts")
    if not isinstance(counts, dict) or not counts or restore.get("tables_verified") != len(counts):
        raise ValueError("restored application table inventory differs from the backup manifest")
    if restore.get("archives_verified") != 2:
        raise ValueError("restored object and Markdown archives were not both verified")
    if not manifest.get("alembicHead") or restore.get("alembic_head") != manifest["alembicHead"]:
        raise ValueError("restored Alembic head differs from the backup manifest")
    if restore.get("rdkit_function_probe") != "passed":
        raise ValueError("restored RDKit function probe did not pass")
    if restore.get("backup_postgres_image_id") != manifest.get("postgresImageId"):
        raise ValueError("restore evidence does not belong to the backup PostgreSQL image")
    expected_image = target_image or manifest["postgresImageId"]
    if restore.get("restored_postgres_image_id") != expected_image:
        raise ValueError("restore did not verify the requested PostgreSQL image")
    if restore.get("postgres_image_changed") is not (expected_image != manifest["postgresImageId"]):
        raise ValueError("restore PostgreSQL image-change evidence is inconsistent")
    authority, artifacts = manifest.get("authority"), manifest.get("artifacts")
    if (
        not isinstance(authority, list)
        or len(authority) < 6
        or not all(isinstance(name, str) for name in authority)
        or len(set(authority)) != len(authority)
        or not isinstance(artifacts, dict)
    ):
        raise ValueError("backup authority manifest is incomplete")
    for name in authority:
        metadata = artifacts.get(name)
        size = metadata.get("sizeBytes") if isinstance(metadata, dict) else None
        if type(size) is not int or size < 1:
            raise ValueError(f"backup artifact metadata is invalid: {name}")
    schema, version, validate = load_contract()
    report = {
        "schema": schema,
        "schema_version": version,
        "generated_at": restore.get("created_at"),
        "status": "passed",
        "environment": "local-wsl",
        "production_claim": False,
        "credentials_recorded": False,
        "backup_reference": reference,
        "backup_manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "backup_checksums_sha256": hashlib.sha256(checksums_path.read_bytes()).hexdigest(),
        "authority_artifacts": len(authority),
        "authority_bytes": sum(artifacts[name]["sizeBytes"] for name in authority),
        "tables_verified": restore["tables_verified"],
        "alembic_head": restore["alembic_head"],
        "rdkit_version": restore.get("rdkit_version"),
        "rdkit_function_probe": restore["rdkit_function_probe"],
        "backup_postgres_image_id": restore["backup_postgres_image_id"],
        "restored_postgres_image_id": restore["restored_postgres_image_id"],
        "postgres_image_changed": restore["postgres_image_changed"],
        "temporal_databases_restored": restore["temporal_databases_restored"],
        "rls_probe": restore["rls_probe"],
        "archives_verified": restore["archives_verified"],
        "main_runtime_modified": False,
        "duration_seconds": duration,
        "sensitive_backup_embedded": False,
    }
    validate(report)
    return report


def write_exclusive(output: Path, payload: bytes) -> None:
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
            raise ValueError(f"refusing to overwrite backup/restore evidence: {output}") from exc
        directory_fd = os.open(output.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> None:
    if len(sys.argv) != 9:
        raise ValueError(
            "usage: runtime_backup_report.py MANIFEST CHECKSUMS RESTORE BACKUP AUTHORITY DURATION OUTPUT TARGET"
        )
    manifest, checksums, restored, backup, authority, duration, output, target = sys.argv[1:]
    report = build_report(
        Path(manifest), Path(checksums), Path(restored), Path(backup), Path(authority), int(duration), target
    )
    payload = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode()
    if output:
        write_exclusive(Path(output), payload)
    sys.stdout.buffer.write(payload)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as exc:
        raise SystemExit(str(exc)) from exc
