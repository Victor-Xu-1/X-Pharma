"""Dependency-free backup report contract shared by producers and readers."""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import datetime
from pathlib import PurePosixPath

BACKUP_RESTORE_SCHEMA_V1 = "pharma.local-backup-restore-acceptance.v1"
BACKUP_RESTORE_SCHEMA = "pharma.local-backup-restore-acceptance.v2"
BACKUP_RESTORE_SCHEMA_VERSION = 2
BACKUP_RESTORE_FIELDS_V1 = frozenset(
    {
        "schema",
        "schema_version",
        "generated_at",
        "status",
        "environment",
        "production_claim",
        "credentials_recorded",
        "backup_reference",
        "backup_manifest_sha256",
        "backup_checksums_sha256",
        "authority_artifacts",
        "authority_bytes",
        "tables_verified",
        "alembic_head",
        "rdkit_version",
        "temporal_databases_restored",
        "rls_probe",
        "archives_verified",
        "main_runtime_modified",
        "duration_seconds",
        "sensitive_backup_embedded",
    }
)
BACKUP_RESTORE_FIELDS = BACKUP_RESTORE_FIELDS_V1 | {
    "rdkit_function_probe",
    "backup_postgres_image_id",
    "restored_postgres_image_id",
    "postgres_image_changed",
}
_CONTRACTS = {
    1: (BACKUP_RESTORE_SCHEMA_V1, BACKUP_RESTORE_FIELDS_V1),
    BACKUP_RESTORE_SCHEMA_VERSION: (BACKUP_RESTORE_SCHEMA, BACKUP_RESTORE_FIELDS),
}


def validate_backup_restore_report(report: Mapping[str, object]) -> int:
    """Validate data semantics, not physical execution, freshness or release approval."""
    version = report.get("schema_version")
    if type(version) is not int or version not in _CONTRACTS:
        raise ValueError("backup restore report has an invalid local scope or status")
    schema, fields = _CONTRACTS[version]
    if (
        set(report) != fields
        or report.get("schema") != schema
        or report.get("status") not in ("passed", "failed")
        or report.get("environment") != "local-wsl"
        or report.get("production_claim") is not False
        or report.get("credentials_recorded") is not False
    ):
        raise ValueError("backup restore report has an invalid local scope or status")
    timestamp = report.get("generated_at")
    try:
        parsed = datetime.fromisoformat(timestamp) if isinstance(timestamp, str) else None
    except ValueError as exc:
        raise ValueError("backup restore generated_at is invalid") from exc
    if parsed is None or parsed.tzinfo is None:
        raise ValueError("backup restore generated_at is invalid")
    reference = report.get("backup_reference")
    path = PurePosixPath(reference) if isinstance(reference, str) else PurePosixPath("/")
    # Custom engineering roots remain valid; release admission applies its
    # additional release-candidates boundary separately.
    if (
        not isinstance(reference, str)
        or "\\" in reference
        or any(ord(character) < 32 or ord(character) == 127 for character in reference)
        or path.as_posix() != reference
        or path.is_absolute()
        or ".." in path.parts
        or len(path.parts) < 2
        or path.parts[0] != "backups"
    ):
        raise ValueError("backup restore authority reference is unsafe")
    for field in ("backup_manifest_sha256", "backup_checksums_sha256"):
        value = report.get(field)
        if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
            raise ValueError("backup restore authority digests are invalid")
    for field, minimum in (("authority_artifacts", 6), ("authority_bytes", 1), ("tables_verified", 1)):
        value = report.get(field)
        if type(value) is not int or value < minimum:
            raise ValueError("backup restore authority inventory is incomplete")
    head = report.get("alembic_head")
    if (
        not isinstance(head, str)
        or re.fullmatch(r"[a-z0-9]{1,64}", head) is None
        or report.get("rdkit_version") != "4.8.0"
        or type(report.get("temporal_databases_restored")) is not int
        or report.get("temporal_databases_restored") != 2
        or report.get("rls_probe") != "passed"
        or report.get("archives_verified") != 2
        or type(report.get("archives_verified")) is not int
        or report.get("main_runtime_modified") is not False
        or report.get("sensitive_backup_embedded") is not False
    ):
        raise ValueError("backup restore authority assertions are incomplete")
    if version == BACKUP_RESTORE_SCHEMA_VERSION:
        backup_image = report.get("backup_postgres_image_id")
        restored_image = report.get("restored_postgres_image_id")
        changed = report.get("postgres_image_changed")
        if (
            not isinstance(backup_image, str)
            or re.fullmatch(r"sha256:[0-9a-f]{64}", backup_image) is None
            or not isinstance(restored_image, str)
            or re.fullmatch(r"sha256:[0-9a-f]{64}", restored_image) is None
            or type(changed) is not bool
            or changed is not (backup_image != restored_image)
            or report.get("rdkit_function_probe") != "passed"
        ):
            raise ValueError("backup restore image identity or RDKit function assertions are incomplete")
    duration = report.get("duration_seconds")
    if type(duration) is not int or not 0 < duration <= 3600:
        raise ValueError("backup restore duration is invalid")
    return version
