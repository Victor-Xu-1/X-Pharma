from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Any

from scripts.release.contracts.core import SHA256_PATTERN, UUID_PATTERN
from scripts.release.contracts.mcp import (
    MCP_INTEROPERABILITY_FIELDS,
    MCP_INTEROPERABILITY_REPORT,
    MCP_INTEROPERABILITY_SCHEMA,
    MCP_INTEROPERABILITY_TOOL_COUNT,
    MCP_INTEROPERABILITY_WORKFLOW_ASSERTIONS,
)
from scripts.release.io import _load_json_object, _parse_timestamp
from scripts.release.records import EvidencePolicy, ReleaseEvidenceError


def _validate_mcp_interoperability_evidence(
    statement_path: Path,
    statement: dict[str, Any],
    *,
    policy: EvidencePolicy | None,
) -> None:
    raw_attachments = statement.get("attachments")
    if not isinstance(raw_attachments, list):
        raise ReleaseEvidenceError("MCP interoperability attachments are invalid")
    reports = [
        item for item in raw_attachments if isinstance(item, dict) and item.get("path") == MCP_INTEROPERABILITY_REPORT
    ]
    if len(reports) != 1:
        raise ReleaseEvidenceError("MCP interoperability requires exactly one report.json attachment")
    report = _load_json_object(
        statement_path.parent / MCP_INTEROPERABILITY_REPORT,
        "MCP interoperability report",
    )
    if (
        set(report) != MCP_INTEROPERABILITY_FIELDS
        or report.get("schema") != MCP_INTEROPERABILITY_SCHEMA
        or report.get("schema_version") != 3
        or report.get("status") != "passed"
        or report.get("environment") != "local-wsl-controlled-fixture"
        or report.get("production_claim") is not False
        or report.get("credentials_recorded") is not False
        or report.get("client") != "MCP Inspector + Python MCP SDK"
        or report.get("client_count") != 2
    ):
        raise ReleaseEvidenceError("MCP interoperability report has an invalid local scope or status")
    statement_time = _parse_timestamp(statement.get("generated_at"), "MCP interoperability statement generated_at")
    report_time = _parse_timestamp(report.get("created_at"), "MCP interoperability created_at")
    maximum_age_hours = policy.categories["mcp_protocol"] if policy is not None else 168
    if report_time > statement_time + timedelta(minutes=5) or statement_time - report_time > timedelta(
        hours=maximum_age_hours
    ):
        raise ReleaseEvidenceError("MCP interoperability report is outside the allowed evidence window")
    query_digest = report.get("query_sha256")
    contract_digest = report.get("tool_contract_sha256")
    pagination_digest = report.get("pagination_entity_ids_sha256")
    target_id = report.get("target_id")
    if (
        not isinstance(query_digest, str)
        or SHA256_PATTERN.fullmatch(query_digest) is None
        or not isinstance(contract_digest, str)
        or SHA256_PATTERN.fullmatch(contract_digest) is None
        or not isinstance(pagination_digest, str)
        or SHA256_PATTERN.fullmatch(pagination_digest) is None
        or not isinstance(target_id, str)
        or UUID_PATTERN.fullmatch(target_id) is None
        or report.get("inspector_version") != "0.22.0"
        or report.get("python_sdk_version") != "1.28.1"
        or report.get("protocol_version") != "2025-11-25"
        or report.get("tools") != MCP_INTEROPERABILITY_TOOL_COUNT
        or report.get("pageable_cursor_tools") != 16
        or report.get("billed_calls") != 10
        or report.get("pagination_pages") != 2
        or report.get("pagination_unique_entities") != 2
        or report.get("invalid_cursor_rejected") is not True
        or report.get("recovered_after_error") is not True
        or not isinstance(report.get("competitive_program_items"), int)
        or isinstance(report.get("competitive_program_items"), bool)
        or report["competitive_program_items"] < 1
        or report.get("cross_domain_tool") != "get_competitive_pipeline"
        or report.get("workflow_assertions") != MCP_INTEROPERABILITY_WORKFLOW_ASSERTIONS
    ):
        raise ReleaseEvidenceError("MCP interoperability protocol or tool contract is invalid")
    clients = report.get("clients")
    if not isinstance(clients, list) or len(clients) != 2:
        raise ReleaseEvidenceError("MCP interoperability client inventory is incomplete")
    clients_by_name = {
        client.get("client"): client
        for client in clients
        if isinstance(client, dict) and isinstance(client.get("client"), str)
    }
    if set(clients_by_name) != {"MCP Inspector", "Python MCP SDK"}:
        raise ReleaseEvidenceError("MCP interoperability client inventory is incomplete")
    inspector = clients_by_name["MCP Inspector"]
    sdk = clients_by_name["Python MCP SDK"]
    if set(inspector) != {
        "billed_calls",
        "client",
        "pageable_cursor_tools",
        "query_sha256",
        "status",
        "target_id",
        "tool_contract_sha256",
        "tools",
        "usage_settlements",
        "pagination_pages",
        "pagination_unique_entities",
        "pagination_entity_ids_sha256",
        "invalid_cursor_rejected",
        "recovered_after_error",
        "competitive_program_items",
        "cross_domain_tool",
    } or set(sdk) != {
        "billed_calls",
        "client",
        "client_version",
        "protocol_version",
        "query_sha256",
        "server_name",
        "server_version",
        "status",
        "target_id",
        "tool_contract_sha256",
        "tools",
        "usage_settlements",
        "pagination_pages",
        "pagination_unique_entities",
        "pagination_entity_ids_sha256",
        "invalid_cursor_rejected",
        "recovered_after_error",
        "competitive_program_items",
        "cross_domain_tool",
    }:
        raise ReleaseEvidenceError("MCP interoperability client report fields are invalid")
    for client in (inspector, sdk):
        if (
            client.get("status") != "passed"
            or client.get("query_sha256") != query_digest
            or client.get("target_id") != target_id
            or client.get("tool_contract_sha256") != contract_digest
            or client.get("tools") != MCP_INTEROPERABILITY_TOOL_COUNT
            or client.get("billed_calls") != 5
            or client.get("pagination_pages") != 2
            or client.get("pagination_unique_entities") != 2
            or client.get("pagination_entity_ids_sha256") != pagination_digest
            or client.get("invalid_cursor_rejected") is not True
            or client.get("recovered_after_error") is not True
            or not isinstance(client.get("competitive_program_items"), int)
            or isinstance(client.get("competitive_program_items"), bool)
            or client["competitive_program_items"] < 1
            or client.get("cross_domain_tool") != "get_competitive_pipeline"
            or not isinstance(client.get("usage_settlements"), int)
            or isinstance(client.get("usage_settlements"), bool)
            or client["usage_settlements"] < 5
        ):
            raise ReleaseEvidenceError("MCP interoperability clients did not prove the same billed contract")
    if (
        inspector.get("pageable_cursor_tools") != 16
        or sdk.get("client_version") != "1.28.1"
        or sdk.get("server_name") != "Pharma Intelligence"
        or sdk.get("server_version") != "1.28.1"
        or sdk.get("protocol_version") != "2025-11-25"
        or report.get("usage_settlements") != max(inspector["usage_settlements"], sdk["usage_settlements"])
    ):
        raise ReleaseEvidenceError("MCP interoperability version or settlement evidence is inconsistent")
