from __future__ import annotations

import re
from datetime import timedelta
from pathlib import Path
from typing import Any

from scripts.release.contracts.core import COMMIT_PATTERN, SHA256_PATTERN
from scripts.release.contracts.security import (
    CLEAN_SOURCE_CHECKS,
    CLEAN_SOURCE_COMMANDS,
    CLEAN_SOURCE_REPORT,
    CLEAN_SOURCE_SCHEMA,
)
from scripts.release.io import _load_json_object, _parse_timestamp
from scripts.release.records import EvidencePolicy, ReleaseEvidenceError


def _validate_clean_source_evidence(
    statement_path: Path,
    statement: dict[str, Any],
    *,
    policy: EvidencePolicy | None,
) -> None:
    raw_attachments = statement.get("attachments")
    if not isinstance(raw_attachments, list):
        raise ReleaseEvidenceError("clean-source evidence attachments are invalid")
    report_metadata = [
        item for item in raw_attachments if isinstance(item, dict) and item.get("path") == CLEAN_SOURCE_REPORT
    ]
    if len(report_metadata) != 1:
        raise ReleaseEvidenceError(f"clean-source evidence requires exactly one {CLEAN_SOURCE_REPORT} attachment")
    report = _load_json_object(statement_path.parent / CLEAN_SOURCE_REPORT, "clean-source report")
    if (
        report.get("schema") != CLEAN_SOURCE_SCHEMA
        or report.get("schema_version") != 1
        or report.get("status") != "passed"
    ):
        raise ReleaseEvidenceError("clean-source report has an invalid schema or status")

    statement_subject = statement.get("subject")
    report_subject = report.get("subject")
    if not isinstance(statement_subject, dict) or not isinstance(report_subject, dict):
        raise ReleaseEvidenceError("clean-source report subject is invalid")
    expected_subject = {
        "git_commit": statement_subject.get("git_commit"),
        "source_file_count": statement_subject.get("source_file_count"),
        "source_tree_sha256": statement_subject.get("source_tree_sha256"),
    }
    if report_subject != expected_subject:
        raise ReleaseEvidenceError("clean-source report is not bound to the release source")
    if (
        not isinstance(expected_subject["git_commit"], str)
        or COMMIT_PATTERN.fullmatch(expected_subject["git_commit"]) is None
        or not isinstance(expected_subject["source_file_count"], int)
        or isinstance(expected_subject["source_file_count"], bool)
        or expected_subject["source_file_count"] < 1
        or not isinstance(expected_subject["source_tree_sha256"], str)
        or SHA256_PATTERN.fullmatch(expected_subject["source_tree_sha256"]) is None
    ):
        raise ReleaseEvidenceError("clean-source report contains an invalid source identity")

    statement_time = _parse_timestamp(statement.get("generated_at"), "clean-source statement generated_at")
    report_time = _parse_timestamp(report.get("generated_at"), "clean-source report generated_at")
    maximum_age_hours = policy.categories["source_reproducibility"] if policy is not None else 168
    if report_time > statement_time + timedelta(minutes=5) or statement_time - report_time > timedelta(
        hours=maximum_age_hours
    ):
        raise ReleaseEvidenceError("clean-source report is outside the allowed evidence window")

    checks = report.get("checks")
    if (
        not isinstance(checks, dict)
        or set(checks) != CLEAN_SOURCE_CHECKS
        or not all(value is True for value in checks.values())
    ):
        raise ReleaseEvidenceError("clean-source report did not pass every contracted check")
    image_digest = report.get("application_image_digest")
    if (
        not isinstance(image_digest, str)
        or re.fullmatch(r"sha256:[0-9a-f]{64}", image_digest) is None
        or report.get("application_image_user") != "app"
    ):
        raise ReleaseEvidenceError("clean-source report has an invalid non-root image result")

    commands = report.get("commands")
    if not isinstance(commands, list) or len(commands) != len(CLEAN_SOURCE_COMMANDS):
        raise ReleaseEvidenceError("clean-source report has an incomplete command inventory")
    labels: list[str] = []
    for command in commands:
        if not isinstance(command, dict):
            raise ReleaseEvidenceError("clean-source report has an invalid command result")
        label = command.get("label")
        duration_ms = command.get("duration_ms")
        if (
            not isinstance(label, str)
            or command.get("exit_code") != 0
            or not isinstance(duration_ms, int)
            or isinstance(duration_ms, bool)
            or duration_ms < 0
            or duration_ms > 3_600_000
        ):
            raise ReleaseEvidenceError("clean-source report has an invalid command result")
        labels.append(label)
    if tuple(labels) != CLEAN_SOURCE_COMMANDS:
        raise ReleaseEvidenceError("clean-source report command inventory does not match the contract")
