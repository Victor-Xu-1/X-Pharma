from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Any

from scripts.release.contracts.core import SHA256_PATTERN, UUID_PATTERN
from scripts.release.contracts.data import (
    RECORD_CONSISTENCY_FIELDS,
    RECORD_CONSISTENCY_MCP_TOOLS,
    RECORD_CONSISTENCY_REPORT,
    RECORD_CONSISTENCY_SCHEMA,
    RECORD_CONSISTENCY_WEB_OPERATIONS,
)
from scripts.release.io import _load_json_object, _parse_timestamp
from scripts.release.records import EvidencePolicy, ReleaseEvidenceError


def _validate_record_consistency_evidence(
    statement_path: Path,
    statement: dict[str, Any],
    *,
    policy: EvidencePolicy | None,
) -> None:
    raw_attachments = statement.get("attachments")
    if not isinstance(raw_attachments, list):
        raise ReleaseEvidenceError("record consistency attachments are invalid")
    reports = [
        item for item in raw_attachments if isinstance(item, dict) and item.get("path") == RECORD_CONSISTENCY_REPORT
    ]
    if len(reports) != 1:
        raise ReleaseEvidenceError("record consistency requires exactly one report.json attachment")
    report = _load_json_object(statement_path.parent / RECORD_CONSISTENCY_REPORT, "record consistency report")
    if (
        set(report) != RECORD_CONSISTENCY_FIELDS
        or report.get("schema") != RECORD_CONSISTENCY_SCHEMA
        or report.get("schema_version") != 1
        or report.get("status") != "passed"
        or report.get("environment") != "local-wsl-isolated-postgresql"
        or report.get("production_claim") is not False
        or report.get("controlled_fixture") is not True
        or report.get("credentials_recorded") is not False
    ):
        raise ReleaseEvidenceError("record consistency report has an invalid scope or status")
    statement_time = _parse_timestamp(statement.get("generated_at"), "record consistency statement generated_at")
    report_time = _parse_timestamp(report.get("generated_at"), "record consistency generated_at")
    maximum_age_hours = policy.categories["record_consistency"] if policy is not None else 168
    if report_time > statement_time + timedelta(minutes=5) or statement_time - report_time > timedelta(
        hours=maximum_age_hours
    ):
        raise ReleaseEvidenceError("record consistency report is outside the allowed evidence window")
    identity_fields = (
        "activity_id",
        "target_id",
        "provenance_id",
        "source_version_id",
        "source_document_id",
    )
    if any(
        not isinstance(report.get(field), str) or UUID_PATTERN.fullmatch(report[field]) is None
        for field in identity_fields
    ):
        raise ReleaseEvidenceError("record consistency authority identifiers are invalid")
    digest_fields = ("activity_sha256", "provenance_sha256", "export_row_sha256")
    if any(
        not isinstance(report.get(field), str) or SHA256_PATTERN.fullmatch(report[field]) is None
        for field in digest_fields
    ):
        raise ReleaseEvidenceError("record consistency canonical digests are invalid")
    source_locator = report.get("source_locator")
    if not isinstance(source_locator, str) or not 1 <= len(source_locator) <= 500:
        raise ReleaseEvidenceError("record consistency source locator is invalid")
    web_operations = report.get("web_operations")
    mcp_tools = report.get("mcp_tools")
    if (
        not isinstance(web_operations, list)
        or len(web_operations) != len(RECORD_CONSISTENCY_WEB_OPERATIONS)
        or set(web_operations) != RECORD_CONSISTENCY_WEB_OPERATIONS
        or not isinstance(mcp_tools, list)
        or len(mcp_tools) != len(RECORD_CONSISTENCY_MCP_TOOLS)
        or set(mcp_tools) != RECORD_CONSISTENCY_MCP_TOOLS
        or report.get("mcp_protocol_version") != "2025-11-25"
    ):
        raise ReleaseEvidenceError("record consistency protocol operation inventory is incomplete")
    if (
        report.get("billed_operations") != 3
        or report.get("unique_settlements") != 3
        or report.get("export_dataset") != "fact_provenance"
        or report.get("export_record_count") != 1
        or report.get("export_manifest_verified") is not True
        or report.get("same_authority_identifiers") is not True
        or report.get("same_source_version") is not True
        or report.get("same_source_locator") is not True
    ):
        raise ReleaseEvidenceError("record consistency authority or commercial assertions are incomplete")
    cleanup = report.get("cleanup")
    if cleanup != {"api_stopped": True, "mcp_stopped": True, "database_dropped": True}:
        raise ReleaseEvidenceError("record consistency isolated runtime cleanup is incomplete")
