from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Any

from scripts.release.contracts.security import (
    ANTI_EXTRACTION_BASELINE_ASSERTIONS,
    ANTI_EXTRACTION_BASELINE_FIELDS,
    ANTI_EXTRACTION_BASELINE_REPORT,
    ANTI_EXTRACTION_BASELINE_SCENARIOS,
    ANTI_EXTRACTION_BASELINE_SCHEMA,
)
from scripts.release.io import _load_json_object, _parse_timestamp
from scripts.release.records import EvidencePolicy, ReleaseEvidenceError


def _validate_anti_extraction_baseline_evidence(
    statement_path: Path,
    statement: dict[str, Any],
    *,
    policy: EvidencePolicy | None,
) -> None:
    raw_attachments = statement.get("attachments")
    if not isinstance(raw_attachments, list):
        raise ReleaseEvidenceError("anti-extraction baseline attachments are invalid")
    reports = [
        item
        for item in raw_attachments
        if isinstance(item, dict) and item.get("path") == ANTI_EXTRACTION_BASELINE_REPORT
    ]
    if len(reports) != 1:
        raise ReleaseEvidenceError("anti-extraction baseline requires exactly one report.json attachment")
    report = _load_json_object(
        statement_path.parent / ANTI_EXTRACTION_BASELINE_REPORT,
        "anti-extraction baseline report",
    )
    if (
        set(report) != ANTI_EXTRACTION_BASELINE_FIELDS
        or report.get("schema") != ANTI_EXTRACTION_BASELINE_SCHEMA
        or report.get("schema_version") != 1
        or report.get("status") != "passed"
        or report.get("environment") != "local-wsl-isolated-postgresql"
        or report.get("production_claim") is not False
        or report.get("controlled_fixture") is not True
        or report.get("credentials_recorded") is not False
        or report.get("auth_profile") != "isolated-database-api-key"
        or report.get("production_oidc_covered") is not False
        or report.get("protocol_version") != "2025-11-25"
    ):
        raise ReleaseEvidenceError("anti-extraction baseline report has an invalid scope or status")
    statement_time = _parse_timestamp(statement.get("generated_at"), "anti-extraction statement generated_at")
    report_time = _parse_timestamp(report.get("generated_at"), "anti-extraction generated_at")
    maximum_age_hours = policy.categories["anti_extraction_baseline"] if policy is not None else 168
    if report_time > statement_time + timedelta(minutes=5) or statement_time - report_time > timedelta(
        hours=maximum_age_hours
    ):
        raise ReleaseEvidenceError("anti-extraction baseline report is outside the allowed evidence window")
    if report.get("scenarios") != ANTI_EXTRACTION_BASELINE_SCENARIOS:
        raise ReleaseEvidenceError("anti-extraction baseline scenario inventory is incomplete")
    assertions = report.get("assertions")
    if (
        not isinstance(assertions, dict)
        or set(assertions) != ANTI_EXTRACTION_BASELINE_ASSERTIONS
        or not all(value is True for value in assertions.values())
    ):
        raise ReleaseEvidenceError("anti-extraction baseline assertions are incomplete")
    database = report.get("database")
    expected_database_fields = {
        "durable_denial_reason_count",
        "successful_settlement_count",
        "active_reservations_after",
        "unauthorized_export_jobs_created",
        "credential_revocation_audit_events",
        "raw_partition_values_persisted",
        "raw_correlation_values_persisted",
    }
    settlements = database.get("successful_settlement_count") if isinstance(database, dict) else None
    if (
        not isinstance(database, dict)
        or set(database) != expected_database_fields
        or database.get("durable_denial_reason_count") != 4
        or not isinstance(settlements, int)
        or isinstance(settlements, bool)
        or settlements < 9
        or database.get("active_reservations_after") != 0
        or database.get("unauthorized_export_jobs_created") != 0
        or database.get("credential_revocation_audit_events") != 1
        or database.get("raw_partition_values_persisted") is not False
        or database.get("raw_correlation_values_persisted") is not False
    ):
        raise ReleaseEvidenceError("anti-extraction baseline durable database evidence is incomplete")
    if report.get("cleanup") != {"api_stopped": True, "mcp_stopped": True, "database_dropped": True}:
        raise ReleaseEvidenceError("anti-extraction baseline isolated runtime cleanup is incomplete")
    duration = report.get("duration_seconds")
    if not isinstance(duration, int | float) or isinstance(duration, bool) or not 0 < duration <= 600:
        raise ReleaseEvidenceError("anti-extraction baseline duration is invalid")
