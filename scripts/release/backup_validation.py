from __future__ import annotations

import re
from datetime import timedelta
from pathlib import Path, PurePosixPath
from typing import Any

from pharma_intel.platform.backup_contract import validate_backup_restore_report
from scripts.release.contracts.migrations import known_migration_revisions
from scripts.release.contracts.platform import BACKUP_RESTORE_REPORT
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
    try:
        version = validate_backup_restore_report(report)
    except ValueError as exc:
        raise ReleaseEvidenceError(str(exc)) from exc
    if report.get("status") != "passed":
        raise ReleaseEvidenceError("backup restore report has an invalid local scope or status")
    minimum = policy.minimum_report_schema_versions.get("backup_restore", 1) if policy is not None else 1
    if version < minimum:
        raise ReleaseEvidenceError("backup restore report schema is older than the policy minimum")
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
    if version == 1 and report.get("alembic_head") != "5d7e1a3c9b24":
        raise ReleaseEvidenceError("backup restore authority assertions are incomplete")
    if version == 2:
        try:
            known = known_migration_revisions(Path(__file__).resolve().parents[2])
        except Exception as exc:  # Alembic can raise multiple malformed-graph exception families; never fall back.
            raise ReleaseEvidenceError("candidate migration authority is unavailable") from exc
        # Restoring a recorded ancestor is valid rollback evidence, not proof
        # that the live candidate has applied its current migration head.
        if report["alembic_head"] not in known:
            raise ReleaseEvidenceError("backup restore authority assertions reference an unknown migration")
        if report["postgres_image_changed"]:
            subject = statement.get("subject")
            targets = subject.get("targets") if isinstance(subject, dict) else None
            postgres = targets.get("postgres") if isinstance(targets, dict) else None
            if (
                not isinstance(postgres, str)
                or re.fullmatch(r"[^@\s]+@sha256:[0-9a-f]{64}", postgres) is None
                or report["restored_postgres_image_id"] != postgres.rsplit("@", maxsplit=1)[1]
            ):
                raise ReleaseEvidenceError("backup restore target is not the security-scanned PostgreSQL subject")
