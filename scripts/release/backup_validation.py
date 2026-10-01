from __future__ import annotations

from datetime import timedelta
from pathlib import Path, PurePosixPath
from typing import Any

from scripts.release.contracts.core import SHA256_PATTERN
from scripts.release.contracts.platform import BACKUP_RESTORE_FIELDS, BACKUP_RESTORE_REPORT, BACKUP_RESTORE_SCHEMA
from scripts.release.io import _load_json_object, _parse_timestamp
from scripts.release.records import EvidencePolicy, ReleaseEvidenceError


def _validate_backup_restore_evidence(
    statement_path: Path,
    statement: dict[str, Any],
    *,
    policy: EvidencePolicy | None,
) -> None:
    raw_attachments = statement.get("attachments")
    if not isinstance(raw_attachments, list):
        raise ReleaseEvidenceError("backup restore attachments are invalid")
    reports = [item for item in raw_attachments if isinstance(item, dict) and item.get("path") == BACKUP_RESTORE_REPORT]
    if len(reports) != 1:
        raise ReleaseEvidenceError("backup restore evidence requires exactly one report.json attachment")
    report = _load_json_object(statement_path.parent / BACKUP_RESTORE_REPORT, "backup restore report")
    if (
        set(report) != BACKUP_RESTORE_FIELDS
        or report.get("schema") != BACKUP_RESTORE_SCHEMA
        or report.get("schema_version") != 1
        or report.get("status") != "passed"
        or report.get("environment") != "local-wsl"
        or report.get("production_claim") is not False
        or report.get("credentials_recorded") is not False
    ):
        raise ReleaseEvidenceError("backup restore report has an invalid local scope or status")
    statement_time = _parse_timestamp(statement.get("generated_at"), "backup restore statement generated_at")
    report_time = _parse_timestamp(report.get("generated_at"), "backup restore generated_at")
    maximum_age_hours = policy.categories["backup_restore"] if policy is not None else 168
    if report_time > statement_time + timedelta(minutes=5) or statement_time - report_time > timedelta(
        hours=maximum_age_hours
    ):
        raise ReleaseEvidenceError("backup restore report is outside the allowed evidence window")
    reference_text = report.get("backup_reference")
    reference = PurePosixPath(reference_text) if isinstance(reference_text, str) else PurePosixPath("/")
    if (
        reference.is_absolute()
        or ".." in reference.parts
        or len(reference.parts) < 3
        or reference.parts[:2] != ("backups", "release-candidates")
    ):
        raise ReleaseEvidenceError("backup restore authority reference is unsafe")
    if any(
        not isinstance(report.get(field), str) or SHA256_PATTERN.fullmatch(report[field]) is None
        for field in ("backup_manifest_sha256", "backup_checksums_sha256")
    ):
        raise ReleaseEvidenceError("backup restore authority digests are invalid")
    integer_minimums = {
        "authority_artifacts": 6,
        "authority_bytes": 1,
        "tables_verified": 1,
    }
    if any(
        not isinstance(report.get(field), int) or isinstance(report[field], bool) or report[field] < minimum
        for field, minimum in integer_minimums.items()
    ):
        raise ReleaseEvidenceError("backup restore authority inventory is incomplete")
    if (
        report.get("alembic_head") != "5d7e1a3c9b24"
        or report.get("rdkit_version") != "4.8.0"
        or report.get("temporal_databases_restored") != 2
        or report.get("rls_probe") != "passed"
        or report.get("archives_verified") != 2
        or report.get("main_runtime_modified") is not False
        or report.get("sensitive_backup_embedded") is not False
    ):
        raise ReleaseEvidenceError("backup restore authority assertions are incomplete")
    duration = report.get("duration_seconds")
    if not isinstance(duration, int) or isinstance(duration, bool) or not 0 < duration <= 3600:
        raise ReleaseEvidenceError("backup restore duration is invalid")
