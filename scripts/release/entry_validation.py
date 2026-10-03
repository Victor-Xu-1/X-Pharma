from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Any

from scripts.release.contracts.browser import (
    ENTRY_CONSISTENCY_ENTITY_FIELDS,
    ENTRY_CONSISTENCY_FIELDS,
    ENTRY_CONSISTENCY_REPORT,
    ENTRY_CONSISTENCY_SCHEMA,
)
from scripts.release.contracts.core import SHA256_PATTERN, UUID_PATTERN
from scripts.release.io import _load_json_object, _parse_timestamp
from scripts.release.records import EvidencePolicy, ReleaseEvidenceError


def _validate_entry_consistency_evidence(
    statement_path: Path,
    statement: dict[str, Any],
    *,
    policy: EvidencePolicy | None,
) -> None:
    raw_attachments = statement.get("attachments")
    if not isinstance(raw_attachments, list):
        raise ReleaseEvidenceError("entry consistency attachments are invalid")
    reports = [
        item for item in raw_attachments if isinstance(item, dict) and item.get("path") == ENTRY_CONSISTENCY_REPORT
    ]
    if len(reports) != 1:
        raise ReleaseEvidenceError("entry consistency requires exactly one report.json attachment")
    report = _load_json_object(statement_path.parent / ENTRY_CONSISTENCY_REPORT, "entry consistency report")
    if (
        set(report) != ENTRY_CONSISTENCY_FIELDS
        or report.get("schema") != ENTRY_CONSISTENCY_SCHEMA
        or report.get("schema_version") != 1
        or report.get("status") != "passed"
        or report.get("environment") != "local-wsl-controlled-fixture"
        or report.get("production_claim") is not False
        or report.get("credentials_recorded") is not False
    ):
        raise ReleaseEvidenceError("entry consistency report has an invalid local scope or status")
    statement_time = _parse_timestamp(statement.get("generated_at"), "entry consistency statement generated_at")
    report_time = _parse_timestamp(report.get("generated_at"), "entry consistency generated_at")
    maximum_age_hours = policy.categories["entry_consistency"] if policy is not None else 168
    if report_time > statement_time + timedelta(minutes=5) or statement_time - report_time > timedelta(
        hours=maximum_age_hours
    ):
        raise ReleaseEvidenceError("entry consistency report is outside the allowed evidence window")
    entity_id = report.get("entity_id")
    digest = report.get("canonical_entity_sha256")
    if (
        not isinstance(entity_id, str)
        or UUID_PATTERN.fullmatch(entity_id) is None
        or not isinstance(digest, str)
        or SHA256_PATTERN.fullmatch(digest) is None
    ):
        raise ReleaseEvidenceError("entry consistency fixture identity is invalid")
    if (
        report.get("fields_compared") != list(ENTRY_CONSISTENCY_ENTITY_FIELDS)
        or report.get("web_operations") != ["create_entity", "get_entity", "search_entities"]
        or report.get("mcp_tools") != ["get_entity", "search_entities"]
        or report.get("mcp_protocol_version") != "2025-11-25"
        or report.get("mcp_billed_calls") != 2
        or report.get("unique_settlements") != 2
        or report.get("same_tenant_fixture") is not True
        or report.get("same_filtered_facts") is not True
        or report.get("temporary_accounts_after") != 0
        or report.get("temporary_entities_after") != 0
    ):
        raise ReleaseEvidenceError("entry consistency Web, MCP, billing, or cleanup assertions are incomplete")
